import yaml
import boto3
import time

class deploy_cluster:
    
    def __init__(self,filename):
    
        with open(filename) as file:
          config_data = yaml.load(file, Loader=yaml.FullLoader)
        #return config_data


        ########## Create Cluster 

          cluster_name = (config_data.get('cluster')['clustername'])
          role_arn = (config_data.get('cluster')['rolearn'])

          subnet_ids = (config_data.get('cluster')['subnetids'])
          security_group_ids = (config_data.get('cluster')['securitygroupids'])

          response = self.create_eks_cluster(cluster_name, role_arn, subnet_ids, security_group_ids)

          print(response)

        ## Sleep for 10 minutes to allow the cluster to be created
          time.sleep(600)

        ## Check if the cluster is active

          while  self.cluster_status(cluster_name) != 'ACTIVE':
              print('Waiting for Cluster to be in active state')
              time.sleep(60)

        ########### Node groups

          for i in config_data.get('nodegroups'):
            print((i)['name'])
            node_group_name = (i)['name']
            instance_type = (i)['instanceType']
            minSize = (i)['minSize']
            maxSize = (i)['maxSize']
            desiredSize = (i)['desiredCapacity']
            amiType = (i)['amiType']
            diskSize = (i)['volumeSize']
            capacityType = (i)['capacityType']
            subnet_ids = config_data.get('cluster')['subnetids']
            role_arn = (i)['noderolearn']
            response = self.create_node_group(cluster_name, node_group_name, instance_type, minSize, maxSize, desiredSize, amiType, diskSize, capacityType, subnet_ids, role_arn)
            print(response)


    def create_eks_cluster(self, cluster_name, role_arn, subnet_ids, security_group_ids):
        eks_client = boto3.client('eks')
        
        response = eks_client.create_cluster(
            name=cluster_name,
            roleArn=role_arn,
            resourcesVpcConfig={
                'subnetIds': subnet_ids,
                'securityGroupIds': security_group_ids
            }
        )
        
        return response

###############

    def create_node_group(self, cluster_name, node_group_name, instance_type, minSize, maxSize, desiredSize, amiType, diskSize, capacityType, subnet_ids, role_arn):

        eks_client = boto3.client('eks')

        #print(eks_client.describe_cluster(name=cluster_name))

        response = eks_client.create_nodegroup(
            clusterName=cluster_name,
            nodegroupName=node_group_name,
            scalingConfig={
                'minSize': minSize,
                'maxSize': maxSize,
                'desiredSize': desiredSize
            },
            diskSize=diskSize,
            subnets=subnet_ids,
            instanceTypes=[
                instance_type,
            ],
            amiType=amiType,
            nodeRole=role_arn,
            tags={
                'clusterName' : cluster_name
            },
            updateConfig={
                'maxUnavailable': 1,
            },
            capacityType=capacityType,
        )

        return response

    def cluster_status(self, cluster_name):
        eks_client = boto3.client('eks')
        response = eks_client.describe_cluster(name=cluster_name)
        return response['cluster']['status']

    def delete_nodegroup(cluster_name, nodegroup_name):
        eks_client = boto3.client('eks')
        response = eks_client.delete_nodegroup(
            clusterName=cluster_name,
            nodegroupName=nodegroup_name
        )
        return response

    def delete_cluster(cluster_name):
        eks_client = boto3.client('eks')
        response = eks_client.delete_cluster(
            name=cluster_name
        )
        return response
    
########## Read YAML file


### deploy cluster


    # Usage:

    #     # Initialize the Create class
    #     create_instance.__init__()

    #deploy_cluster('clu-config.yaml')

    # delete node group

    #deploy_cluster.delete_nodegroup('eks-4', 'ngrp2')

    # delete cluster    

    #deploy_cluster.delete_cluster('eks-4')

    # Author:
    #     Harshad Pitkar
    # """
