import yaml
import boto3
import time
import sys
import botocore
import os
import paramiko


from cloudmesh.common.StopWatch import StopWatch
from cloudmesh.common.console import Console
from cloudmesh.common.util import path_expand


class Cluster:
    
    def __init__(self, config=None, cluster_name=None, dryrun=False):
        """
        Initializes the cluster
        
        Args:
            config (str): The path to the configuration file
            cluster_name (str): The name of the cluster
            dryrun (bool): If True, the function does not run
            
        """


        if config is None:
            config = path_expand(config)
        try:
            with open(config) as file:
                self.config_data = yaml.load(file, Loader=yaml.FullLoader)
        except FileNotFoundError:
            Console.error(f"The specified file does not exist.")
            sys.exit()

        self.config = config
        #return config_data

        if dryrun:
            Console.msg(f"DRY RUN of create {config}")
            return
        else:
            Cluster.setup(self,name=cluster_name)

        
    def setup(self, dt=6,name=None):
        """
        Sets up all the pre-requisites before creating the cluster

        Args:
            name (str): The name of the cluster
        """

        pcsClusterRoleName = 'AWSPCS-ClusterRole'

        iam_client = boto3.client('iam')

        if self.check_pcs_iam_roles(pcsClusterRoleName) == "NoSuchEntity":
            self.create_pcs_iam_role(pcsClusterRoleName)
            policy_details = self.create_pcs_iam_policy("awspcs-cluster-policy")
            policy_arn = (policy_details["Policy"]["Arn"])
            attach_status = self.attach_pcs_iam_policy(pcsClusterRoleName, policy_arn)
        try:    
            role_arn = self.check_pcs_iam_roles(pcsClusterRoleName)
        except botocore.exceptions.ClientError as e:
            Console.error(f"Error getting PCS cluster role: {e}")
            sys.exit()


        # Check if instance profile exists, if not create it.
        iam_client = boto3.client('iam')


        InstanceProfileName = "AWSPCS-instance-profile"

        try:
            response = iam_client.create_instance_profile(
                            InstanceProfileName = InstanceProfileName,
                            Tags=[
                                {
                                    'Key': 'description',
                                    'Value': 'Instance profile for Parallel Cluster'
                                },
                            ]
                        )
        except botocore.exceptions.ClientError as e:
            if e.response['Error']['Code'] == 'EntityAlreadyExists':    
                response = iam_client.get_instance_profile(
                            InstanceProfileName = InstanceProfileName
                            )
            else:
                Console.error(f"Error creating instance profile: {e}")
                sys.exit()
        instance_profile_arn = response['InstanceProfile']['Arn']
        try:
            response = iam_client.add_role_to_instance_profile(
                InstanceProfileName = InstanceProfileName,
                RoleName = pcsClusterRoleName
            )
        except botocore.exceptions.ClientError as e:
            if e.response['Error']['Code'] == 'LimitExceeded':    
                pass
            else:
                Console.error(f"Error adding role to instance profile: {e}")
                sys.exit()

        # check if launch template exists, if not create it
        ec2_client = boto3.client('ec2')

        create_launch_template_flag = False

        LaunchTemplateName = 'awspcs-launch-template-' + name

        try:
            response = ec2_client.describe_launch_templates(
                LaunchTemplateNames=[
                    LaunchTemplateName
                ]
            )

            launch_template = response['LaunchTemplates'][0]['LaunchTemplateId']
            template_version = response['LaunchTemplates'][0]['LatestVersionNumber']

        except botocore.exceptions.ClientError as e:
            if e.response['Error']['Code'] == 'InvalidLaunchTemplateName.NotFoundException':
                create_launch_template_flag = True
            elif e.response['Error']['Code'] == 'InvalidLaunchTemplateName.AlreadyExistsException':
                create_launch_template_flag = False
            else:
                Console.error(f"launch template does not exist: {e}")
                sys.exit()

        # Security group
        security_group_name = name + 'sg'

        try:
            security_group_id = Cluster.create_security_group(name, security_group_name)
        except botocore.exceptions.ClientError as e:
            if e.response['Error']['Code'] == 'InvalidGroup.Duplicate':
                security_group_id = Cluster.get_security_group(security_group_name)
            else:
                Console.error(f"Error creating security group: {e}")
                sys.exit()

        keypair_name = name + '-keypair'
        
        try:
            keypair_response = Cluster.create_keypair(self, keypair_name)
            
            f = open(keypair_name, "a")
            f.write(keypair_response["KeyMaterial"])
            f.close()

            print("Important: CLuster login information saved to .pem file")
        except botocore.exceptions.ClientError as e:
            if e.response['Error']['Code'] == 'InvalidKeyPair.Duplicate':
                pass
            else:
                Console.error(f"Error creating keypair: {e}")
                sys.exit()


        user_data_script = "" # add base64 encoded user data script here if you want to mount shared file system

        if create_launch_template_flag == True:
            response = ec2_client.create_launch_template(
                LaunchTemplateName = LaunchTemplateName,
                LaunchTemplateData={
                    'BlockDeviceMappings': [
                        {
                            'DeviceName': '/dev/xvda',
                            'Ebs': {
                                'VolumeSize': 128
                            }
                        }
                    ],
                    'KeyName': keypair_name, 
                    'SecurityGroupIds': [security_group_id],
                    'UserData': user_data_script
                }
       
            )
            launch_template = response['LaunchTemplate']['LaunchTemplateId']
            template_version = response['LaunchTemplate']['LatestVersionNumber']

            
        size = self.config_data.get('cloudmesh')['cluster']['aws']['size']
  
        cluster_name = name

        try:
            subnet_ids = self.get_subnets(public_private_subnet='public')
        except botocore.exceptions.ClientError as e:
            Console.error(f"Error getting EKS subnets: {e}")
            sys.exit()


        try:
            response = self.create_parallel_cluster(subnet_ids, security_group_id, cluster_name, size)
        except botocore.exceptions.ClientError as e:
            Console.error(f"Error creating EKS cluster: {e}")
            sys.exit()

        ## Sleep for 10 minutes to allow the cluster to be created
        time.sleep(dt)

        ## Check if the cluster is active

        while  self.cluster_status(cluster_name) != 'ACTIVE':
            print('Waiting for Cluster to be in active state')
            time.sleep(60)

        ## Node groups


        for nodegroup in self.config_data.get('cloudmesh')['cluster']['aws']['nodegroups']:
          
          node_group_name = (nodegroup)['name']
          instance_type = (nodegroup)['instanceType']
          minSize = 0 
          maxSize = (nodegroup)['desiredCapacity']
          capacityType = (nodegroup)['capacityType']
          subnet_ids = subnet_ids
          
          try:
            response = self.create_nodegroup(cluster_name, 
                                             node_group_name, 
                                             instance_type, 
                                             launch_template, 
                                             template_version, 
                                             instance_profile_arn,
                                             minSize, 
                                             maxSize, 
                                             capacityType,
                                             subnet_ids)
          except botocore.exceptions.ClientError as e:
            Console.error(f"Error creating node group for parallel cluster: {e}")
            sys.exit()

          # create queues

          try:
            response = self.create_queue(cluster_name, node_group_name)
          except botocore.exceptions.ClientError as e:
            Console.error(f"Error creating PCS job queue: {e}")
            sys.exit()

        # finally create a static nodegoup for login/head node with public subnet(s)
          minSize = 1
          maxSize = 1
          subnet_ids = self.get_subnets(public_private_subnet='public')
          try:
              response = self.create_nodegroup(cluster_name, 'login', 
                                               instance_type, 
                                               launch_template, 
                                               template_version, 
                                               instance_profile_arn,
                                               minSize, maxSize, capacityType,
                                               subnet_ids)
          except botocore.exceptions.ClientError as e:
            Console.error(f"Error creating node group for parallel cluster: {e}")
            sys.exit()


        clusterinfo = Cluster.info(cluster_name)
        print(clusterinfo)

    def create_queue(self, cluster_name=None, node_group_name=None, dt=30):
        """
        Creates a queue for the cluster
        
        Args:
            cluster_name (str): The name of the cluster
            node_group_name (str): The name of the node group
        """

        pcs_client = boto3.client('pcs')

        status = ""

        try:                
            while status != 'ACTIVE':
                try:
                    nodegroup_status = pcs_client.get_compute_node_group(
                        clusterIdentifier = cluster_name,
                        computeNodeGroupIdentifier = node_group_name
                    )
                    print(nodegroup_status)
                    status = nodegroup_status['computeNodeGroup']['status']
                    if status != 'ACTIVE':
                        print('Waiting for Node Group to be Active')
                        time.sleep(dt)
                except botocore.exceptions.ClientError as e:
                    if e.response['Error']['Code'] == 'AccessDeniedException':
                        Console.error(f"Check if the PCS node group exists: {e}")
                        sys.exit()
        except botocore.exceptions.ClientError as e:
            Console.error(f"Error getting PCS node group info: {e}")
            sys.exit()

        try:
            response = pcs_client.create_queue(
                clusterIdentifier = cluster_name,
                queueName = node_group_name + '-queue',
                computeNodeGroupConfigurations = [
                    {
                        'computeNodeGroupId': nodegroup_status['computeNodeGroup']['id'],
                    }
                ]
            )
        except botocore.exceptions.ClientError as e:
            Console.error(f"Error creating PCS job queue: {e}")
            sys.exit()

        return response

    def cluster_status(self, cluster_name):
        """
        Gets the status of the cluster

        Args:
            cluster_name (str): The name of the cluster
        """

        pcs_client = boto3.client('pcs')
        response = pcs_client.get_cluster(clusterIdentifier=cluster_name)
        return response['cluster']['status']

    def delete(self, name, dryrun=False, dt=60):
        """
        Deletes the cluster
        
        Args:
            name (str): The name of the cluster
            dryrun (bool): If True, the function does not run
        """

        pcs_client = boto3.client('pcs')

        try:
            response = pcs_client.list_queues(
               clusterIdentifier = name,
            )
        except botocore.exceptions.ClientError as e:
            Console.error(f"Error listing PCS queues: {e}")
            sys.exit()

        for queues in response['queues']:
            try:
                response = pcs_client.delete_queue(
                    clusterIdentifier = name,
                    queueIdentifier = queues['name']
                )
            except botocore.exceptions.ClientError as e:
                Console.error(f"Error deleting PCS queue: {e}")
                sys.exit()

        try:
            response = pcs_client.list_compute_node_groups(
                                clusterIdentifier = name
                         )
        except botocore.exceptions.ClientError as e:
            Console.error(f"Error listing PCS node groups: {e}")
            sys.exit()
        
        time.sleep(180)

        for nodegroup in response['computeNodeGroups']:
            try:
                response = pcs_client.delete_compute_node_group(
                    clusterIdentifier = name,
                    computeNodeGroupIdentifier = nodegroup['name']
                )

                deletion_status = ""

                try:                
                    while deletion_status != 'DELETED':
                        try:
                            nodegroup_status = pcs_client.get_compute_node_group(
                                clusterIdentifier = name,
                                computeNodeGroupIdentifier = nodegroup['name']
                            )
                            deletion_status = nodegroup_status['computeNodeGroup']['status']
                        except botocore.exceptions.ClientError as e:
                            if e.response['Error']['Code'] == 'AccessDeniedException':
                                deletion_status = 'DELETED'
                            else:
                                Console.error(f"Error getting PCS node group info: {e}")
                                sys.exit()

                        print('Waiting for Node Group to be deleted')
                        time.sleep(dt)
                except botocore.exceptions.ClientError as e:
                    Console.error(f"Error getting PCS node group info: {e}")
                    sys.exit()


            except botocore.exceptions.ClientError as e:
                Console.error(f"Error deleting PCS node group: {e}")
                sys.exit()


        try:
            response = pcs_client.delete_cluster(
                            clusterIdentifier = name
                      )
        except botocore.exceptions.ClientError as e:
            Console.error(f"Error deleting PCS cluster: {e}")
            sys.exit()
        
        return response
    
    def get_subnets(self, public_private_subnet=None):
        """
        Gets the subnet Ids of the cluster
        
        Args:
            public_private_subnet (str): The type of subnet, public or private
        """

        ec2_client = boto3.client('ec2')
        print(public_private_subnet)
        if public_private_subnet == 'public':
            public_subnet = 'true'
        else:
            public_subnet = 'false'
        
        try:
            response = ec2_client.describe_subnets(
                Filters=[
                    {
                        'Name': 'map-public-ip-on-launch', 
                        'Values': [public_subnet]
                    }
                ]
            )
        except botocore.exceptions.ClientError as e:
            Console.error(f"Error getting subnets: {e}")
            sys.exit()
        
        subnet1 = ''
        subnet2 = ''

        for sn in response['Subnets'] :
            
            if not subnet1:
                subnet1 = sn['SubnetId']
                az1 = sn['AvailabilityZoneId']

            if az1 != sn['AvailabilityZoneId']:
                subnet2 = sn['SubnetId']
                break
            
        return [subnet1, subnet2]
        

    def create_parallel_cluster(self,subnetid,security_group_id,name=None,size='SMALL'):
        """
        Creates a PCS cluster
        
        Args:
            name (str): The name of the cluster
            size (str): The size of the cluster
            security_group_id (str): The security group Id
            subnetid (list): The list of subnet Ids
        """
        pcs_client = boto3.client('pcs')
        
        security_group_id = security_group_id
        subnetid = subnetid

        try:
            response = pcs_client.create_cluster(
                clusterName = name,
                scheduler = {
                    'type': 'SLURM',
                    'version': '23.11'
                },
                networking = {
                    'subnetIds' : [subnetid[0]],
                    'securityGroupIds': [security_group_id]
                },
                size = size  # 'SMALL' # SMALL | MEDIUM | LARGE | XLARGE | CUSTOM
            )
        except botocore.exceptions.ClientError as e:
            Console.error(f"Error creating PCS cluster: {e}")
            sys.exit()
        
        return response

    def create_nodegroup(self,name=None, 
                         node_group_name=None, 
                         instance_type=None, 
                         launch_template=None, 
                         template_version=None, 
                         instance_profile=None, 
                         minSize=None, maxSize=None, 
                         capacityType=None, 
                         subnet_ids=None): 
        """
        Creates a node group for the cluster
        
        Args:
        
            name (str): The name of the cluster
            node_group_name (str): The name of the node group
            instance_type (str): The instance type
            launch_template (str): The launch template
            template_version (int): The version of the launch template
            instance_profile (str): The instance profile
            minSize (int): The minimum size of the node group
            maxSize (int): The maximum size of the node group
            capacityType (str): The capacity type
            subnet_ids (list): The list of subnet Ids
        """

        pcs_client = boto3.client('pcs')
        
        try:
            response = pcs_client.create_compute_node_group(
                clusterIdentifier = name,
                computeNodeGroupName = node_group_name,
                amiId = 'ami-0febaafa7a4bf06e2',
                subnetIds = subnet_ids,
                scalingConfiguration={
                    'minInstanceCount': minSize,
                    'maxInstanceCount': maxSize
                },
                purchaseOption = capacityType, # ON_DEMAND | SPOT
                customLaunchTemplate = {
                'id': launch_template,
                'version': str(template_version)
                },
                iamInstanceProfileArn = instance_profile,
                instanceConfigs = [
                    {
                        'instanceType': instance_type
                    }
                ],
            )
        except botocore.exceptions.ClientError as e:
            Console.error(f"Error creating PCS node group: {e}")
            sys.exit()
        
        #return response
        print(response)

    def get_vpc():
        """
        Gets the VPC Id of the cluster
        
        Args:
            None
        """

        ec2 = boto3.client('ec2')

        try:
            response = ec2.describe_vpcs()
        except botocore.exceptions.ClientError as e:
            Console.error(f"Error getting VPC: {e}")
            sys.exit()
        return response["Vpcs"][0]["VpcId"]

    def create_security_group(clusterName=None, security_group_name=None):
        """
        Creates a security group for the cluster
        
        Args:
            clusterName (str): The name of the cluster
            security_group_name (str): The name of the security group
        """

        ec2_client = boto3.client('ec2')
        cluster_name = clusterName # pass this later when you include in init
        vpc_id = Cluster.get_vpc()

        try:
            response = ec2_client.create_security_group(
                Description='Security Group fo HPC Cluster',
                GroupName = security_group_name, #+ round(time.time()), # pass the cluster name here
                VpcId = vpc_id, # this call is placed here temporarily, will be move to init later
                TagSpecifications=[
                    {
                        'ResourceType': 'security-group',
                        'Tags': [
                        {
                            'Key': 'clusterName',
                            'Value': cluster_name
                        },
                            ]
                    },
                ],
            )
        except botocore.exceptions.ClientError as e:
            Console.error(f"Error creating security group: {e}")
            sys.exit()

        try:
            response_rule = ec2_client.authorize_security_group_ingress(
                    DryRun=False,
                    GroupId=response["GroupId"], 
                    IpPermissions=[
                        { 
                            #'FromPort': 443,
                            'IpProtocol': '-1',
                            'IpRanges': [
                                {
                                    'CidrIp': '0.0.0.0/0',
                                    'Description': 'Security group updated via lambda'
                                }
                            ],
                    #      'ToPort': 443
                        }
                    ]
                )
        except botocore.exceptions.ClientError as e:
            Console.error(f"Error adding ingress rule to security group: {e}")
            sys.exit()

        return response["GroupId"]

    def get_security_group(security_group_name=None):
        """
        Gets the security group Id of the cluster
        
        Args:
            security_group_name (str): The name of the security group
        """

        ec2_client = boto3.client('ec2')
        
        try:
            response = ec2_client.describe_security_groups(
                Filters= [
                    {
                        'Name': 'group-name',
                        'Values': [
                            security_group_name,
                        ]
                    },
                ],
            )
        except botocore.exceptions.ClientError as e:
            Console.error(f"Error getting security group: {e}")
            sys.exit()

        return response["SecurityGroups"][0]["GroupId"]

    def check_pcs_iam_roles(self, role_name):
        iam_client = boto3.client('iam')
        
        """
        Checks if an IAM role exists.
        Args:
            role_name (str): The name of the IAM role.
        Returns:
            str: The Amazon Resource Name (ARN) of the IAM role.
        Raises:
            botocore.exceptions.ClientError: If there is an error getting the IAM role.
        """

        try:
            response = iam_client.get_role(
               RoleName=role_name
            )

        except iam_client.exceptions.NoSuchEntityException:
            response = "NoSuchEntity"
            return response
        except botocore.exceptions.ClientError as e:
            Console.error(f"Unable to find EKS role for the account: {e}")
            sys.exit()

        return response["Role"]["Arn"]

    def create_pcs_iam_policy(self, policy_name):
        """
        Creates an IAM policy for an Amazon EKS cluster.
        Args:
            policy_name (str): The name of the IAM policy.
            Returns:
            dict: A dictionary containing the response from the create_policy API call.
            Raises:
            botocore.exceptions.ClientError: If there is an error creating the IAM policy.
        """
        
        iam_client = boto3.client('iam')
        try:
            response = iam_client.create_policy(
                            PolicyName = policy_name,
                            PolicyDocument = '''{
                                                    "Version": "2012-10-17", 
                                                    "Statement": [
                                                        {
                                                        "Action": ["pcs:RegisterComputeNodeGroupInstance"],
                                                        "Resource": "*",
                                                        "Effect": "Allow"
                                                        }
                                                    ]
                                                }'''
            )
        except botocore.exceptions.ClientError as e:
            Console.error(f"Error creating PCS IAM policy: {e}")
            sys.exit()

        return response

    def create_pcs_iam_role(self, role_name):
        """
        Creates an IAM role for an Amazon EKS cluster.
        Args:
            role_name (str): The name of the IAM role.
            Returns:
            dict: A dictionary containing the response from the create_role API call.
            Raises:
            botocore.exceptions.ClientError: If there is an error creating the IAM role.
        """
        iam_client = boto3.client('iam')

        assume_role_policy_document = '''{
                                            "Version": "2012-10-17",
                                            "Statement": [
                                                {
                                                "Effect": "Allow",
                                                "Principal": {"Service": "ec2.amazonaws.com"},
                                                "Action": "sts:AssumeRole"
                                                }
                                            ]
                                        }'''
        
        try:
            response = iam_client.create_role(  
                RoleName = role_name, 
                AssumeRolePolicyDocument = assume_role_policy_document,
                Description = "PCS Role created by Cloudmesh"
            )
        except botocore.exceptions.ClientError as e:
            Console.error(f"Error creating PCS IAM role: {e}")
            sys.exit()

    def attach_pcs_iam_policy(self, role_name, policy_arn):
        """
        Attaches an IAM policy to an IAM role.
        Args:
            role_name (str): The name of the IAM role.
            policy_name (str): The name of the IAM policy.
            Returns:
            dict: A dictionary containing the response from the attach_role_policy API call.
            Raises:
            botocore.exceptions.ClientError: If there is an error attaching the IAM policy.
        """

        iam_client = boto3.client('iam')
        try:
            response = iam_client.attach_role_policy(
                RoleName = role_name,
                PolicyArn = policy_arn
            )
        except botocore.exceptions.ClientError as e:
            Console.error(f"Error attaching PCS IAM policy: {e}")
            sys.exit()

        return response

    def create_keypair(self, key_name):
        """
        Creates a keypair for the cluster

        Args:
            key_name (str): The name of the keypair
        """

        ec2_client = boto3.client('ec2')
        try:
            keypair_response = ec2_client.create_key_pair(KeyName=key_name)
        except botocore.exceptions.ClientError as e:
            Console.error(f"Error creating keypair: {e}")
            sys.exit()
        return keypair_response

    def info(name, source=None, update=False, dryrun=False):
        """
        Gets the information of the cluster
        
        Args:
            name (str): The name of the cluster
            source (str): The source of the cluster information, local or remote
            update (bool): If True, the function updates the cluster information
        """

        pcs_client = boto3.client('pcs')
        file_name = name + 'info.txt'
        if source == 'local' and update == False:
            f = open(file_name, "r")
            contents = f.read()
            f.close()
            print("local")
            return contents
        elif source == 'remote' or update == True:
            try:
                response = pcs_client.get_cluster(
                    clusterIdentifier = name
                )
                f = open(file_name, "w")
                f.write(yaml.dump(response))
                f.close()
                return response
            except botocore.exceptions.ClientError as e:
                Console.error(f"Error getting PCS cluster info: {e}")
                sys.exit()


    def get_login_node_id(cluster_name=None):
        """
        Gets the login node Id of the cluster

        Args:
            cluster_name (str): The name of the cluster
        """

        ec2_client = boto3.client('ec2')
        pcs_client = boto3.client('pcs')
        node_group_name = 'login'
    
        try:
            nodegroup_id = pcs_client.get_compute_node_group(
                clusterIdentifier = cluster_name,
                computeNodeGroupIdentifier = node_group_name
            )
        except botocore.exceptions.ClientError as e:
            Console.error(f"Error getting login node group Id: {e}")
            sys.exit()

        try:
    
            login_node = ec2_client.describe_instances(
                Filters=[
                {
                    'Name': 'tag:aws:pcs:compute-node-group-id', #name', 
                    'Values': [nodegroup_id['computeNodeGroup']['id']]
                }
                    ]
            )
    
            login_node_id = login_node['Reservations'][0]['Instances'][0]['PublicDnsName']
            return login_node_id
        except botocore.exceptions.ClientError as e:
            Console.error(f"Error getting login node Id: {e}")
            sys.exit()

    def run(cluster_name=None, port=None, rwd=None, scriptname=None, dryrun=False):        
        """
        Runs the script on the login node of the cluster

        Args:
            cluster_name (str): The name of the cluster
            port (int): The port number for ssh connection
            rwd (str): The remote working directory
            scriptname (str): The name of the script to run
            dryrun (bool): If True, the function does not run
        """

        cwd=os.getcwd()
        try:
            login_node_name = Cluster.get_login_node_id(cluster_name)
            # created client using paramiko
            client = paramiko.SSHClient()

            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

            client.connect(login_node_name, port, username='ec2-user', key_filename=cwd + '\\' + cluster_name + '-keypair')
            sftp = client.open_sftp()
            sftp.put(scriptname, rwd + 'install.sh')
            sftp.close()
        except Exception as e:
            print(e)



    def uploadkey(cluster_name=None, port=22, sshdir='~/.ssh/', rwd='/home/ec2-user/', dryrun=False):        
        """
        Uploads the public key to the login node of the cluster
        
        Args:
            cluster_name (str): The name of the cluster
            port (int): The port number for ssh connection
            sshdir (str): The path to the ssh directory
            rwd (str): The remote working directory
            dryrun (bool): If True, the function does not run
        """

        print('running pcs uploadkey')
        try:
            login_node_name = Cluster.get_login_node_id(cluster_name)
        
            # generate key:
            sshkeyfile = sshdir / "id_rsa.pub"
            if  os.path.isfile(sshkeyfile):
                print("Public key file exists")
            else:
                print("Public file does not exist; generating one now!")
                import subprocess
                subprocess.call('ssh-keygen', shell=True)

           # created client using paramiko
            client = paramiko.SSHClient()

            client.set_missing_host_key_policy(paramiko.AutoAddPolicy())

            client.connect(login_node_name, port, username='ec2-user', key_filename=sshdir + '\\' + cluster_name + '-keypair')
            sftp = client.open_sftp()

            sftp.put(sshkeyfile, rwd + '/user-pubkey')

            command = "cd ~/.ssh; cat user-pubkey >> authorized_keys"

            stdin, stdout, stderr = client.exec_command(command)
            #subprocess.call(command, shell=True)
            print ("stderr: ", stderr.readlines())
            print ("stdout: ", stdout.readlines())

            sftp.close()
        except Exception as e:  
            print(e)
            print("Error in uploading key")

