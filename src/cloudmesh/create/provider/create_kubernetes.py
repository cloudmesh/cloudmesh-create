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
        """
        Initializes the Create class.
        Args:
            filename (str): The path to the YAML file containing the configuration data for the EKS cluster.
            dt (int): The time to wait for the cluster to be created. Default is 600 seconds (10 minutes).
        Raises:
            FileNotFoundError: If the specified file does not exist.
        """

        if config is None:
            config = path_expand(config)
        try:
            with open(config) as file:
              self.config_data = yaml.load(file, Loader=yaml.FullLoader)
        except FileNotFoundError:
            Console.error("The specified file does not exist.")
            sys.exit()

        self.config = config

        if dryrun:
            Console.msg(f"DRY RUN of create {config}")
            return
        else:
            Cluster.setup(self,name=cluster_name)



    def setup(self,dt=600,name=None):
        """
        Creates an Amazon EKS cluster.
        Args:
            dt (int): The time to wait for the cluster to be created. Default is 600 seconds (10 minutes).
            Raises:
            botocore.exceptions.ClientError: If there is an error creating the EKS cluster.
        """

        # Create Cluster 
        
        # Check if role exists, if not create it.

        if self.check_eks_iam_roles("eksClusterRole") == "NoSuchEntity":
            self.create_eks_iam_role("eksClusterRole")
            self.attach_eks_iam_policy("eksClusterRole", "AmazonEKSClusterPolicy")
        
        try:    
            role_arn = self.check_eks_iam_roles("eksClusterRole")
        except botocore.exceptions.ClientError as e:
            Console.error(f"Error getting EKS cluster role: {e}")
            sys.exit()
        
        cluster_name = name #(self.config_data.get('cloudmesh')['cluster']['aws'][0]['name'])
        print("Cluster Name: " + cluster_name)
        
        try:
            subnet_ids = self.get_subnets_for_eks() 
        except botocore.exceptions.ClientError as e:
            Console.error(f"Error getting EKS subnets: {e}")
            sys.exit()
        
        try:
            response = self.create_default_cluster(cluster_name, role_arn, subnet_ids)
        except botocore.exceptions.ClientError as e:
            Console.error(f"Error creating EKS cluster: {e}")
            sys.exit()

        # Sleep for 10 minutes to allow the cluster to be created
        time.sleep(dt)

        # Check if the cluster is active
        StopWatch.start("cluster")
        while  self.status(cluster_name) != 'ACTIVE':
            print('Waiting for Cluster to be in active state')
            time.sleep(60)
        StopWatch.stop("cluster")
        StopWatch.benchmark()

        # Node groups

        #Check if the node role exists, if not create it.

        if self.check_eks_iam_roles("AmazonEKSNodeRole") == "NoSuchEntity":
            self.create_eks_iam_role("AmazonEKSNodeRole")
            self.attach_eks_iam_policy("AmazonEKSNodeRole", "AmazonEC2ContainerRegistryReadOnly")
            self.attach_eks_iam_policy("AmazonEKSNodeRole", "AmazonEKS_CNI_Policy")
            self.attach_eks_iam_policy("AmazonEKSNodeRole", "AmazonEKSWorkerNodePolicy")
        
        try:    
            noderole_arn = self.check_eks_iam_roles("AmazonEKSNodeRole")
        except botocore.exceptions.ClientError as e:
            Console.error(f"Error getting EKS Node role: {e}")
            sys.exit()

        for nodegroup in self.config_data.get('cloudmesh')['cluster']['aws']['nodegroups']:
          
          node_group_name = (nodegroup)['name']
          instance_type = (nodegroup)['instanceType']
          minSize = (nodegroup)['desiredCapacity']
          maxSize = (nodegroup)['desiredCapacity']
          desiredSize = (nodegroup)['desiredCapacity']
          diskSize = (nodegroup)['volumeSize']
          capacityType = (nodegroup)['capacityType']
          subnet_ids = subnet_ids
          role_arn = noderole_arn
          
          try:
            response = self.create_nodegroup(cluster_name, node_group_name, instance_type,
                                             minSize, maxSize, desiredSize, diskSize, capacityType,
                                             subnet_ids, role_arn)
            print(response)
          except botocore.exceptions.ClientError as e:
            Console.error(f"Error creating EKS node group: {e}")
            sys.exit()
        
        Cluster.info(cluster_name)

        Cluster.cluster_config(cluster_name)


    def create_nodegroup(self,
                         cluster_name,
                         node_group_name,
                         instance_type,
                         minSize,
                         maxSize,
                         desiredSize,
                         diskSize,
                         capacityType,
                         subnet_ids,
                         role_arn):
        """
        Creates an Amazon EKS node group.
        Args:
            cluster_name (str): The name of the EKS cluster.
            node_group_name (str): The name of the node group.
            instance_type (str): The instance type for the node group.
            minSize (int): The minimum number of nodes for the node group.
            maxSize (int): The maximum number of nodes for the node group.
            desiredSize (int): The desired number of nodes for the node group.
            diskSize (int): The size of the disk for the node group.
            capacityType (str): The capacity type for the node group.
            subnet_ids (list): A list of subnet IDs where the node group will be created.
            role_arn (str): The Amazon Resource Name (ARN) of the IAM role that provides permissions for the node group.
        Returns:
            dict: A dictionary containing the response from the create_nodegroup API call.
        Raises:
            botocore.exceptions.ClientError: If there is an error creating the EKS node group.
        """

        eks_client = boto3.client('eks')

        try:
            response = eks_client.create_nodegroup(
                clusterName = cluster_name,
                nodegroupName = node_group_name,
                scalingConfig = {
                    'minSize': minSize,
                    'maxSize': maxSize,
                    'desiredSize': desiredSize
                },
                diskSize = diskSize,
                subnets = subnet_ids,
                instanceTypes = [
                    instance_type,
                ],
                nodeRole = role_arn,
                tags = {
                    'clusterName' : cluster_name
                },
                updateConfig = {
                    'maxUnavailable': 1,
                },
                capacityType = capacityType,
            )
        except botocore.exceptions.ClientError as e:
            Console.error(f"Error creating EKS node group: {e}")
            sys.exit()

        return response

    def status(self, cluster_name):
        """
        Gets the status of an Amazon EKS cluster.
        Args:
            cluster_name (str): The name of the EKS cluster.
        Returns:
            str: The status of the EKS cluster.
        Raises:
            botocore.exceptions.ClientError: If there is an error getting the EKS cluster status.
        """

        eks_client = boto3.client('eks')

        try:
            response = eks_client.describe_cluster(name=cluster_name)
        except botocore.exceptions.ClientError as e:
            Console.error(f"Unable to get EKS cluster status: {e}")
            sys.exit()

        return response['cluster']['status']


    def delete(self, name, dryrun=False):
        """
        Deletes an Amazon EKS cluster.
        Args:
            cluster_name (str): The name of the EKS cluster.
        Returns:
            dict: A dictionary containing the response from the delete_cluster API call.
        Raises:
            botocore.exceptions.ClientError: If there is an error deleting the EKS cluster.
        """

        eks_client = boto3.client('eks')


        try:
            response = eks_client.list_nodegroups(
                                clusterName=name
                         )
        except botocore.exceptions.ClientError as e:
            Console.error(f"Error listing EKS node groups: {e}")
            sys.exit()

        for nodegroup in response['nodegroups']:
            try:
                response = eks_client.delete_nodegroup(
                    clusterName=name,
                    nodegroupName=nodegroup
                )

                waiter = eks_client.get_waiter('nodegroup_deleted')

                waiter.wait(
                    clusterName=name,
                    nodegroupName=nodegroup
                )                
            except botocore.exceptions.ClientError as e:
                Console.error(f"Error deleting EKS node group: {e}")
                sys.exit()

        try:
            response = eks_client.delete_cluster(
                name = name
            )
        except botocore.exceptions.ClientError as e:
            Console.error(f"Error deleting EKS cluster: {e}")
            sys.exit()
        
        return response

    def view_config():

        from pprint import pprint

        pprint (self.config)
        pprint (self.config_data)


    def info(name=None, detail=True, dryrun=False):
        """
        Gets information about an Amazon EKS cluster.
        Args:
            name (str): The name of the EKS cluster.
            detail (bool): A boolean value that determines if additional details are included in the response.
        Returns:
            dict: A dictionary containing the response from the describe_cluster API call.
        Raises:
            botocore.exceptions.ClientError: If there is an error getting the EKS cluster information.
        """

        if dryrun:
            Console.msg(f"INFO DRYRUN {name}")
            return

        try:    
            eks_client = boto3.client('eks')
            response = eks_client.describe_cluster(name=name)
            response = yaml.dump(response['cluster'])
        except botocore.exceptions.ClientError as e:
            Console.error(f"Error getting EKS cluster info: {e}")
            sys.exit()
        
        print(response)
        return response

    def export_config(self, cluster_name, config_file):
        """
        Dumps the configuration of an Amazon EKS cluster to a file.
        Args:
            cluster_name (str): The name of the EKS cluster.
            config_file (str): The path to the file where the cluster information will be dumped.
        Raises:
            FileNotFoundError: If the specified file does not exist.
        """

        eks_client = boto3.client('eks')
        
        try:
            response = eks_client.describe_cluster(name=cluster_name)
        except botocore.exceptions.ClientError as e:
            Console.error(f"Error getting EKS cluster info: {e}")
            sys.exit()
        response = yaml.dump(response['cluster'])

        try:
            with open(config_file, 'w') as file:
                file.write(response)
        except FileNotFoundError:
            Console.error("Unable to write cluster information to file. {config_file}")
            sys.exit()

        print("Cluster information dumped to file: ", config_file)
    

    def create_default_cluster(self,
                               cluster=None,
                               role_arn=None,
                               subnet_ids=None
                              ):
        """
        Creates an Amazon Elastic Kubernetes Service (EKS) cluster.
        Args:
            cluster (str): The name of the EKS cluster.
            role_arn (str): The Amazon Resource Name (ARN) of the IAM role that provides permissions for the EKS cluster.
            subnet_ids (list): A list of subnet IDs where the EKS cluster will be created.
        Returns:
            dict: A dictionary containing the response from the create_cluster API call.
        Raises:
            botocore.exceptions.ClientError: If there is an error creating the EKS cluster.
        """
        print("Creating Default Cluster")

        eks_client = boto3.client('eks')
        
        try:
            response = eks_client.create_cluster(
                name=cluster,
                roleArn=role_arn,
                resourcesVpcConfig={
                     'subnetIds': subnet_ids,
                }
            )
        except botocore.exceptions.ClientError as e:
            Console.error(f"Error creating EKS cluster: {e}")
            sys.exit()

        return response

    def check_eks_iam_roles(self, role_name):
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

    def create_eks_iam_policy(self, policy_name):
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
                PolicyName=policy_name,
                PolicyDocument='''{
                                    "Version": "2012-10-17",
                                    "Statement": [
                                        {
                                            "Effect": "Allow",
                                            "Action": "eks:*",
                                            "Resource": "*"
                                        }
                                    ]
                                }'''
            )
        except botocore.exceptions.ClientError as e:
            Console.error(f"Error creating EKS IAM policy: {e}")
            sys.exit()

        return response

    def create_eks_iam_role(self, role_name):
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

        if role_name == "eksClusterRole":
            assume_role_policy_document = '''{
                                                "Version": "2012-10-17",
                                                "Statement": [
                                                    {
                                                        "Effect": "Allow",
                                                        "Principal": {
                                                            "Service": "eks.amazonaws.com"
                                                            },
                                                        "Action": "sts:AssumeRole"
                                                    }
                                                ]
                                             }'''
            
        elif role_name == "AmazonEKSNodeRole":
            assume_role_policy_document = '''{
                                                "Version": "2012-10-17",
                                                "Statement": [
                                                    {
                                                        "Effect": "Allow",
                                                        "Principal": {
                                                            "Service": "ec2.amazonaws.com"
                                                            },
                                                        "Action": "sts:AssumeRole"
                                                    }
                                                ]
                                            }'''
        
        try:
            response = iam_client.create_role(  
                RoleName = role_name, 
                AssumeRolePolicyDocument = assume_role_policy_document,
                Description = "EKS Role created by Cloudmesh"
            )
        except botocore.exceptions.ClientError as e:
            Console.error(f"Error creating EKS IAM role: {e}")
            sys.exit()

    def attach_eks_iam_policy(self, role_name, policy_name):
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
                RoleName=role_name,
                PolicyArn=f"arn:aws:iam::aws:policy/{policy_name}"
            )
        except botocore.exceptions.ClientError as e:
            Console.error(f"Error attaching EKS IAM policy: {e}")
            sys.exit()

        return response

    def get_subnets_for_eks(self):
        """
        Gets the subnet IDs for an Amazon EKS cluster.
        Returns:
            list: A list of subnet IDs.
        Raises:
            botocore.exceptions.ClientError: If there is an error getting the subnet IDs.
        """

        ec2 = boto3.client('ec2')
        #response = ec2.describe_subnets()
        
        try:
            response = ec2.describe_subnets(
                Filters=[
                    {
                        'Name': 'map-public-ip-on-launch', 
                        'Values': ['true']
                    }
                ]
            )
        except botocore.exceptions.ClientError as e:
            Console.error(f"Error getting EKS subnets: {e}")
            sys.exit()

        subnet1 = ''
        
        for sn in response['Subnets'] :
            
            if not subnet1:
                subnet1 = sn['SubnetId']
                az1 = sn['AvailabilityZoneId']

            if az1 != sn['AvailabilityZoneId']:
                subnet2 = sn['SubnetId']
                break
            
        return [subnet1, subnet2]


    def cluster_config(name=None):
        """
        Exports the configuration of an Amazon EKS cluster to a file.
        Args:
            name (str): The name of the EKS cluster.
            config_file (str): The path to the file where the cluster information will be dumped.
            Raises:
            FileNotFoundError: If the specified file does not exist.
        """
        
        # from eks_token import get_token
        # response = get_token(cluster_name=name)
        # f = open( 'clu-kube-config', "a")
        # f.write(str(response))
        # f.close()

        # print("Cluster configuration exported to config.yaml")
        # print(response)


        eks_client = boto3.client('eks')
        cluster = eks_client.describe_cluster(name=name)
        cluster_cert = cluster["cluster"]["certificateAuthority"]["data"]
        cluster_ep = cluster["cluster"]["endpoint"]

        # build the cluster config hash
        cluster_config = {
                "apiVersion": "v1",
                "kind": "Config",
                "clusters": [
                    {
                        "cluster": {
                            "server": str(cluster_ep),
                            "certificate-authority-data": str(cluster_cert)
                        },
                        "name": "kubernetes"
                    }
                ],
                "contexts": [
                    {
                        "context": {
                            "cluster": name,
                            "user": "aws"
                        },
                        "name": name
                    }
                ],
                "current-context": name,
                "preferences": {},
                "users": [
                    {
                        "name": "aws",
                        "user": {
                            "exec": {
                                "apiVersion": "client.authentication.k8s.io/v1beta1",
                                "command": "aws",
                                "args": [
                                    "token", "-i", name
                                ]
                            }
                        }
                    }
                ]
            }

        # Write in YAML.
        config_text=yaml.dump(cluster_config, default_flow_style=False)
        print("Saving Kube config to config file")
        f = open( '~/.kube/config', "a")
        f.write(config_text)
        f.close()

