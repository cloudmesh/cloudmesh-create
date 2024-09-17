import yaml
import boto3
import time
import sys
import botocore

from cloudmesh.common.StopWatch import StopWatch
from cloudmesh.common.console import Console
from cloudmesh.common.util import path_expand


class Cluster:
    
    def __init__(self, config=None, cluster_name=None, dryrun=False):
    


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

        LaunchTemplateName = 'awspcs-launch-template'

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
            print("Important: CLuster login information, do not forget to securely save these details")
            print(keypair_response)
        except botocore.exceptions.ClientError as e:
            if e.response['Error']['Code'] == 'InvalidKeyPair.Duplicate':
                pass
            else:
                Console.error(f"Error creating keypair: {e}")
                sys.exit()

        if create_launch_template_flag == True:
            response = ec2_client.create_launch_template(
                LaunchTemplateName = LaunchTemplateName,
                LaunchTemplateData={
                    'BlockDeviceMappings': [
                        {
                            'DeviceName': '/dev/sda1',
                            'Ebs': {
                                'VolumeSize': 8
                            }
                        }
                    ],
                    'ImageId': 'ami-0182f373e66f89c85', # hard coded
                    'InstanceType': 't2.micro', # hard coded 
                    'KeyName': keypair_name, 
                    'SecurityGroupIds': [security_group_id] 
                }
       
            )
            launch_template = response['LaunchTemplate']['LaunchTemplateId']
            template_version = response['LaunchTemplate']['LatestVersionNumber']

            
        size = self.config_data.get('cloudmesh')['cluster']['aws']['size']
  
        cluster_name = name

        try:
            subnet_ids = self.get_subnets()
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
          minSize = (nodegroup)['desiredCapacity']
          maxSize = (nodegroup)['desiredCapacity']
          capacityType = (nodegroup)['capacityType']
          subnet_ids = subnet_ids
          
          try:
            response = self.create_nodegroup(cluster_name, node_group_name, instance_type, launch_template, template_version, instance_profile_arn,
                                             minSize, maxSize, capacityType,
                                             subnet_ids)
          except botocore.exceptions.ClientError as e:
            Console.error(f"Error creating node group for parallel cluster: {e}")
            sys.exit()
        
        clusterinfo = Cluster.info(cluster_name)
        print(clusterinfo)


    def cluster_status(self, cluster_name):
        pcs_client = boto3.client('pcs')
        response = pcs_client.get_cluster(clusterIdentifier=cluster_name)
        return response['cluster']['status']

    def delete(self, name, dryrun=False, dt=60):
        pcs_client = boto3.client('pcs')


        try:
            response = pcs_client.list_compute_node_groups(
                                clusterIdentifier = name
                         )
        except botocore.exceptions.ClientError as e:
            Console.error(f"Error listing PCS node groups: {e}")
            sys.exit()
        

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
    
    def get_subnets(self):
        ec2 = boto3.client('ec2')
        response = ec2.describe_subnets()
        
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

        #return response['Subnets'][0]['SubnetId'] + ' ' + response['Subnets'][0]['AvailabilityZoneId']

    def create_parallel_cluster(self,subnetid,security_group_id,name=None,size='SMALL'):

        pcs_client = boto3.client('pcs')
        
        security_group_id = security_group_id
        subnetid = subnetid

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
        
        return response

    def create_nodegroup(self,name=None, node_group_name=None, instance_type=None, launch_template=None, template_version=None, instance_profile=None, minSize=None, maxSize=None, capacityType=None, subnet_ids=None): 
        pcs_client = boto3.client('pcs')
        
        response = pcs_client.create_compute_node_group(
            clusterIdentifier = name,
            computeNodeGroupName = node_group_name,
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
        
        #return response
        print(response)

    def get_vpc():
        ec2 = boto3.client('ec2')
        response = ec2.describe_vpcs()
        return response["Vpcs"][0]["VpcId"]

    def create_security_group(clusterName=None, security_group_name=None):
        ec2 = boto3.client('ec2')
        cluster_name = clusterName # pass this later when you include in init
        response = ec2.create_security_group(
            Description='Security Group fo HPC Cluster',
            GroupName = security_group_name, #+ round(time.time()), # pass the cluster name here
            VpcId = Cluster.get_vpc(), # this call is placed here temporarily, will be move to init later
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

        return response["GroupId"]

    def get_security_group(security_group_name=None):
            ec2_client = boto3.client('ec2')
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
                            PolicyDocument = '{"Version": "2012-10-17", "Statement": [{"Action": ["pcs:RegisterComputeNodeGroupInstance"],"Resource": "*","Effect": "Allow"}]}'
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

        assume_role_policy_document = '{"Version": "2012-10-17","Statement": [{"Effect": "Allow","Principal": {"Service": "ec2.amazonaws.com"},"Action": "sts:AssumeRole"}]}'
        
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
        ec2_client = boto3.client('ec2')
        keypair_response = ec2_client.create_key_pair(KeyName=key_name)
        return keypair_response

    def info(name):
        pcs_client = boto3.client('pcs')

        try:
            response = pcs_client.get_cluster(
                clusterIdentifier = name
            )
        except botocore.exceptions.ClientError as e:
            Console.error(f"Error getting PCS cluster info: {e}")
            sys.exit()

        return response

########## Read YAML file


### deploy cluster


    # Usage:

    #     # Initialize the Create class
    #     create_instance.__init__()

#deploy_cluster('clu-config.yaml')

#deploy_cluster.create_parallel_cluster('pcs1')

#deploy_cluster.create_parallel_nodegroup('pcs1')

    # # create security group

#deploy_cluster.create_security_group()

    # delete node group

    #deploy_cluster.delete_nodegroup('eks-4', 'ngrp2')

    # delete cluster    

    #deploy_cluster.delete_cluster('eks-4')



























########################################################## EKS CLuster ##########################################################

# import yaml
# import boto3
# import time
# import sys
# import botocore

# from cloudmesh.common.StopWatch import StopWatch
# from cloudmesh.common.console import Console
# from cloudmesh.common.util import path_expand

# class Cluster:
        
#     def __init__(self, config=None, cluster_name=None, dryrun=False):
#         """
#         Initializes the Create class.
#         Args:
#             filename (str): The path to the YAML file containing the configuration data for the EKS cluster.
#             dt (int): The time to wait for the cluster to be created. Default is 600 seconds (10 minutes).
#         Raises:
#             FileNotFoundError: If the specified file does not exist.
#         """

#         print("Creating Cluster")
#         print(config)
#         print(cluster_name)

#         if config is None:
#             config = path_expand(config)
#         try:
#             with open(config) as file:
#               self.config_data = yaml.load(file, Loader=yaml.FullLoader)
#         except FileNotFoundError:
#             Console.error("The specified file does not exist.")
#             sys.exit()

#         self.config = config

#         if dryrun:
#             Console.msg(f"DRY RUN of create {config}")
#             return
#         else:
#             Cluster.setup(self,name=cluster_name)



#     def setup(self,dt=600,name=None):

#         # Create Cluster 
        
#         # Check if role exists, if not create it.

#         if self.check_eks_iam_roles("eksClusterRole") == "NoSuchEntity":
#             self.create_eks_iam_role("eksClusterRole")
#             self.attach_eks_iam_policy("eksClusterRole", "AmazonEKSClusterPolicy")
        
#         try:    
#             role_arn = self.check_eks_iam_roles("eksClusterRole")
#         except botocore.exceptions.ClientError as e:
#             Console.error(f"Error getting EKS cluster role: {e}")
#             sys.exit()
        
#         cluster_name = name #(self.config_data.get('cloudmesh')['cluster']['aws'][0]['name'])
#         print("Cluster Name: " + cluster_name)
        
#         try:
#             subnet_ids = self.get_subnets_for_eks() 
#         except botocore.exceptions.ClientError as e:
#             Console.error(f"Error getting EKS subnets: {e}")
#             sys.exit()
        
#         try:
#             response = self.create_default_cluster(cluster_name, role_arn, subnet_ids)
#         except botocore.exceptions.ClientError as e:
#             Console.error(f"Error creating EKS cluster: {e}")
#             sys.exit()

#         # Sleep for 10 minutes to allow the cluster to be created
#         time.sleep(dt)

#         # Check if the cluster is active
#         StopWatch.start("cluster")
#         while  self.status(cluster_name) != 'ACTIVE':
#             print('Waiting for Cluster to be in active state')
#             time.sleep(60)
#         StopWatch.stop("cluster")
#         StopWatch.benchmark()

#         # Node groups

#         #Check if the node role exists, if not create it.

#         if self.check_eks_iam_roles("AmazonEKSNodeRole") == "NoSuchEntity":
#             self.create_eks_iam_role("AmazonEKSNodeRole")
#             self.attach_eks_iam_policy("AmazonEKSNodeRole", "AmazonEC2ContainerRegistryReadOnly")
#             self.attach_eks_iam_policy("AmazonEKSNodeRole", "AmazonEKS_CNI_Policy")
#             self.attach_eks_iam_policy("AmazonEKSNodeRole", "AmazonEKSWorkerNodePolicy")
        
#         try:    
#             noderole_arn = self.check_eks_iam_roles("AmazonEKSNodeRole")
#         except botocore.exceptions.ClientError as e:
#             Console.error(f"Error getting EKS Node role: {e}")
#             sys.exit()

#         for ng in self.config_data.get('cloudmesh')['cluster']['aws']['nodegroups']:
          
#           node_group_name = (ng)['name']
#           instance_type = (ng)['instanceType']
#           minSize = (ng)['desiredCapacity']
#           maxSize = (ng)['desiredCapacity']
#           desiredSize = (ng)['desiredCapacity']
#           diskSize = (ng)['volumeSize']
#           capacityType = (ng)['capacityType']
#           subnet_ids = subnet_ids
#           role_arn = noderole_arn
          
#           try:
#             response = self.create_nodegroup(cluster_name, node_group_name, instance_type,
#                                              minSize, maxSize, desiredSize, diskSize, capacityType,
#                                              subnet_ids, role_arn)
#             print(response)
#           except botocore.exceptions.ClientError as e:
#             Console.error(f"Error creating EKS node group: {e}")
#             sys.exit()
        
#         Cluster.info(cluster_name)


#     def create_nodegroup(self,
#                          cluster_name,
#                          node_group_name,
#                          instance_type,
#                          minSize,
#                          maxSize,
#                          desiredSize,
#                          diskSize,
#                          capacityType,
#                          subnet_ids,
#                          role_arn):
#         """
#         Creates an Amazon EKS node group.
#         Args:
#             cluster_name (str): The name of the EKS cluster.
#             node_group_name (str): The name of the node group.
#             instance_type (str): The instance type for the node group.
#             minSize (int): The minimum number of nodes for the node group.
#             maxSize (int): The maximum number of nodes for the node group.
#             desiredSize (int): The desired number of nodes for the node group.
#             diskSize (int): The size of the disk for the node group.
#             capacityType (str): The capacity type for the node group.
#             subnet_ids (list): A list of subnet IDs where the node group will be created.
#             role_arn (str): The Amazon Resource Name (ARN) of the IAM role that provides permissions for the node group.
#         Returns:
#             dict: A dictionary containing the response from the create_nodegroup API call.
#         Raises:
#             botocore.exceptions.ClientError: If there is an error creating the EKS node group.
#         """

#         eks_client = boto3.client('eks')

#         try:
#             response = eks_client.create_nodegroup(
#                 clusterName = cluster_name,
#                 nodegroupName = node_group_name,
#                 scalingConfig = {
#                     'minSize': minSize,
#                     'maxSize': maxSize,
#                     'desiredSize': desiredSize
#                 },
#                 diskSize = diskSize,
#                 subnets = subnet_ids,
#                 instanceTypes = [
#                     instance_type,
#                 ],
#                 nodeRole = role_arn,
#                 tags = {
#                     'clusterName' : cluster_name
#                 },
#                 updateConfig = {
#                     'maxUnavailable': 1,
#                 },
#                 capacityType = capacityType,
#             )
#         except botocore.exceptions.ClientError as e:
#             Console.error(f"Error creating EKS node group: {e}")
#             sys.exit()

#         return response

#     def status(self, cluster_name):
#         """
#         Gets the status of an Amazon EKS cluster.
#         Args:
#             cluster_name (str): The name of the EKS cluster.
#         Returns:
#             str: The status of the EKS cluster.
#         Raises:
#             botocore.exceptions.ClientError: If there is an error getting the EKS cluster status.
#         """

#         eks_client = boto3.client('eks')

#         try:
#             response = eks_client.describe_cluster(name=cluster_name)
#         except botocore.exceptions.ClientError as e:
#             Console.error(f"Unable to get EKS cluster status: {e}")
#             sys.exit()

#         return response['cluster']['status']


#     def delete(self, name, dryrun=False):
#         """
#         Deletes an Amazon EKS cluster.
#         Args:
#             cluster_name (str): The name of the EKS cluster.
#         Returns:
#             dict: A dictionary containing the response from the delete_cluster API call.
#         Raises:
#             botocore.exceptions.ClientError: If there is an error deleting the EKS cluster.
#         """

#         eks_client = boto3.client('eks')


#         try:
#             response = eks_client.list_nodegroups(
#                                 clusterName=name
#                          )
#         except botocore.exceptions.ClientError as e:
#             Console.error(f"Error listing EKS node groups: {e}")
#             sys.exit()

#         for ng in response['nodegroups']:
#             try:
#                 response = eks_client.delete_nodegroup(
#                     clusterName=name,
#                     nodegroupName=ng
#                 )

#                 waiter = eks_client.get_waiter('nodegroup_deleted')


#                 waiter.wait(
#                     clusterName=name,
#                     nodegroupName=ng
#                 )                
#             except botocore.exceptions.ClientError as e:
#                 Console.error(f"Error deleting EKS node group: {e}")
#                 sys.exit()

#         try:
#             response = eks_client.delete_cluster(
#                 name = name
#             )
#         except botocore.exceptions.ClientError as e:
#             Console.error(f"Error deleting EKS cluster: {e}")
#             sys.exit()
        
#         return response

#     def view_config():

#         from pprint import pprint

#         pprint (self.config)
#         pprint (self.config_data)


#     def info(name=None, detail=True, dryrun=False):
#         """
#         Gets information about an Amazon EKS cluster.
#         Args:
#             name (str): The name of the EKS cluster.
#             detail (bool): A boolean value that determines if additional details are included in the response.
#         Returns:
#             dict: A dictionary containing the response from the describe_cluster API call.
#         Raises:
#             botocore.exceptions.ClientError: If there is an error getting the EKS cluster information.
#         """
#         if dryrun:
#             Console.msg(f"INFO DRYRUN {name}")

#             #Cluster.view_config()

#             return

#         try:    
#             eks_client = boto3.client('eks')
#             response = eks_client.describe_cluster(name=name)
#             response = yaml.dump(response['cluster'])
#         except botocore.exceptions.ClientError as e:
#             Console.error(f"Error getting EKS cluster info: {e}")
#             sys.exit()
        
#         print(response)
#         return response

#     def export_config(self, cluster_name, config_file):
#         """
#         Dumps the configuration of an Amazon EKS cluster to a file.
#         Args:
#             cluster_name (str): The name of the EKS cluster.
#             config_file (str): The path to the file where the cluster information will be dumped.
#         Raises:
#             FileNotFoundError: If the specified file does not exist.
#         """

#         eks_client = boto3.client('eks')
        
#         try:
#             response = eks_client.describe_cluster(name=cluster_name)
#         except botocore.exceptions.ClientError as e:
#             Console.error(f"Error getting EKS cluster info: {e}")
#             sys.exit()
#         response = yaml.dump(response['cluster'])

#         try:
#             with open(config_file, 'w') as file:
#                 file.write(response)
#         except FileNotFoundError:
#             Console.error("Unable to write cluster information to file. {config_file}")
#             sys.exit()

#         print("Cluster information dumped to file: ", config_file)
    

#     def create_default_cluster(self,
#                                cluster=None,
#                                role_arn=None,
#                                subnet_ids=None
#                               ):
#         """
#         Creates an Amazon Elastic Kubernetes Service (EKS) cluster.
#         Args:
#             cluster (str): The name of the EKS cluster.
#             role_arn (str): The Amazon Resource Name (ARN) of the IAM role that provides permissions for the EKS cluster.
#             subnet_ids (list): A list of subnet IDs where the EKS cluster will be created.
#         Returns:
#             dict: A dictionary containing the response from the create_cluster API call.
#         Raises:
#             botocore.exceptions.ClientError: If there is an error creating the EKS cluster.
#         """
#         print("Creating Default Cluster")
#         print(cluster)
#         print(role_arn)
#         print(subnet_ids)

#         eks_client = boto3.client('eks')
        
#         try:
#             response = eks_client.create_cluster(
#                 name=cluster,
#                 roleArn=role_arn,
#                 resourcesVpcConfig={
#                      'subnetIds': subnet_ids,
#                 }
#             )
#         except botocore.exceptions.ClientError as e:
#             Console.error(f"Error creating EKS cluster: {e}")
#             sys.exit()

#         return response

#     def check_eks_iam_roles(self, role_name):
#         iam_client = boto3.client('iam')
        
#         """
#         Checks if an IAM role exists.
#         Args:
#             role_name (str): The name of the IAM role.
#         Returns:
#             str: The Amazon Resource Name (ARN) of the IAM role.
#         Raises:
#             botocore.exceptions.ClientError: If there is an error getting the IAM role.
#         """

#         try:
#             response = iam_client.get_role(
#                RoleName=role_name
#             )

#         except iam_client.exceptions.NoSuchEntityException:
#             response = "NoSuchEntity"
#             return response
#         except botocore.exceptions.ClientError as e:
#             Console.error(f"Unable to find EKS role for the account: {e}")
#             sys.exit()

#         return response["Role"]["Arn"]

#     def create_eks_iam_policy(self, policy_name):
#         """
#         Creates an IAM policy for an Amazon EKS cluster.
#         Args:
#             policy_name (str): The name of the IAM policy.
#             Returns:
#             dict: A dictionary containing the response from the create_policy API call.
#             Raises:
#             botocore.exceptions.ClientError: If there is an error creating the IAM policy.
#         """
        
#         iam_client = boto3.client('iam')
#         try:
#             response = iam_client.create_policy(
#                 PolicyName=policy_name,
#                 PolicyDocument='{"Version": "2012-10-17","Statement": [{"Effect": "Allow","Action": "eks:*","Resource": "*"}]}'
#             )
#         except botocore.exceptions.ClientError as e:
#             Console.error(f"Error creating EKS IAM policy: {e}")
#             sys.exit()

#         return response

#     def create_eks_iam_role(self, role_name):
#         """
#         Creates an IAM role for an Amazon EKS cluster.
#         Args:
#             role_name (str): The name of the IAM role.
#             Returns:
#             dict: A dictionary containing the response from the create_role API call.
#             Raises:
#             botocore.exceptions.ClientError: If there is an error creating the IAM role.
#         """

#         iam_client = boto3.client('iam')

#         if role_name == "eksClusterRole":
#             assume_role_policy_document = '{"Version": "2012-10-17","Statement": [{"Effect": "Allow","Principal": {"Service": "eks.amazonaws.com"},"Action": "sts:AssumeRole"}]}'
#         elif role_name == "AmazonEKSNodeRole":
#             assume_role_policy_document = '{"Version": "2012-10-17","Statement": [{"Effect": "Allow","Principal": {"Service": "ec2.amazonaws.com"},"Action": "sts:AssumeRole"}]}'
        
#         try:
#             response = iam_client.create_role(  
#                 RoleName = role_name, 
#                 AssumeRolePolicyDocument = assume_role_policy_document,
#                 Description = "EKS Role created by Cloudmesh"
#             )
#         except botocore.exceptions.ClientError as e:
#             Console.error(f"Error creating EKS IAM role: {e}")
#             sys.exit()

#     def attach_eks_iam_policy(self, role_name, policy_name):
#         """
#         Attaches an IAM policy to an IAM role.
#         Args:
#             role_name (str): The name of the IAM role.
#             policy_name (str): The name of the IAM policy.
#             Returns:
#             dict: A dictionary containing the response from the attach_role_policy API call.
#             Raises:
#             botocore.exceptions.ClientError: If there is an error attaching the IAM policy.
#         """

#         iam_client = boto3.client('iam')
#         try:
#             response = iam_client.attach_role_policy(
#                 RoleName=role_name,
#                 PolicyArn=f"arn:aws:iam::aws:policy/{policy_name}"
#             )
#         except botocore.exceptions.ClientError as e:
#             Console.error(f"Error attaching EKS IAM policy: {e}")
#             sys.exit()

#         return response

#     def get_subnets_for_eks(self):
#         """
#         Gets the subnet IDs for an Amazon EKS cluster.
#         Returns:
#             list: A list of subnet IDs.
#         Raises:
#             botocore.exceptions.ClientError: If there is an error getting the subnet IDs.
#         """

#         ec2 = boto3.client('ec2')
#         response = ec2.describe_subnets()
        
#         subnet1 = ''
        
#         for sn in response['Subnets'] :
            
#             if not subnet1:
#                 subnet1 = sn['SubnetId']
#                 az1 = sn['AvailabilityZoneId']

#             if az1 != sn['AvailabilityZoneId']:
#                 subnet2 = sn['SubnetId']
#                 break
            
#         return [subnet1, subnet2]

#     # def delete_nodegroup(self, cluster_name, nodegroup_name):
#     #     """
#     #     Deletes an Amazon EKS node group.
#     #     Args:
#     #         cluster_name (str): The name of the EKS cluster.
#     #         nodegroup_name (str): The name of the node group.
#     #     Returns:
#     #         dict: A dictionary containing the response from the delete_nodegroup API call.
#     #     Raises:
#     #         botocore.exceptions.ClientError: If there is an error deleting the EKS node group.
#     #     """

#     #     eks_client = boto3.client('eks')

#     #     try:
#     #         response = eks_client.delete_nodegroup(
#     #             clusterName=cluster_name,
#     #             nodegroupName=nodegroup_name
#     #         )
#     #     except botocore.exceptions.ClientError as e:
#     #         Console.error(f"Error deleting EKS node group: {e}")
#     #         sys.exit()

#     #     return response



#     # Usage:

#     #     # Initialize the Create class
#     #     create_instance.__init__()

# # deploy_cluster('../../../etc/cluster-config.yaml')

# #deploy_cluster.cluster_info('cluster-2')

# #Cluster.info('eks21')

# #Cluster.setup(name='eks21')

# #deploy_cluster.export_cluster_config('cluster-2', 'config.yaml')
#     # delete node group

# #deploy_cluster.delete_nodegroup('cluster-10', 'workers')

#     # delete cluster    

# #deploy_cluster.delete_cluster('cluster-10')

