import boto3
import time

likely not what we need search AWS and HPC Cluster

class HPCCluster:
  
    def __init__(self, region_name='us-west-2'):
        self.ec2 = boto3.resource('ec2', region_name=region_name)
        self.client = boto3.client('ec2', region_name=region_name)

    def create_key_pair(self, key_name):
        try:
            key_pair = self.client.create_key_pair(KeyName=key_name)
            with open(f'{key_name}.pem', 'w') as file:
                file.write(key_pair['KeyMaterial'])
            print(f"Key pair {key_name} created and saved to {key_name}.pem")
        except Exception as e:
            print(f"Error creating key pair: {e}")

    def get_instance_type(self, use_gpu):
        if use_gpu:
            instance_type = 'p3.2xlarge'  # Replace with best suited GPU instance type
        else:
            instance_type = 'c5.9xlarge'  # Replace with best suited CPU instance type
        return instance_type

    def launch_cluster(self, image_id, use_gpu, key_name, security_group_id, instance_count):
        instance_type = self.get_instance_type(use_gpu)
        try:
            instances = self.ec2.create_instances(
                ImageId=image_id,
                InstanceType=instance_type,
                KeyName=key_name,
                MinCount=instance_count,
                MaxCount=instance_count,
                SecurityGroupIds=[security_group_id]
            )
            print(f"Launching {instance_count} instances of type {instance_type}...")
            for instance in instances:
                print(f"Instance ID: {instance.id}")
            
            # Wait for the instances to be running
            for instance in instances:
                instance.wait_until_running()
                instance.reload()
                print(f"Instance {instance.id} is now running.")
            
            return [instance.id for instance in instances]
        except Exception as e:
            print(f"Error launching cluster: {e}")
            return []

    def terminate_cluster(self, instance_ids):
        try:
            self.client.terminate_instances(InstanceIds=instance_ids)
            print("Terminating instances...")
            # Wait for termination to complete
            for instance_id in instance_ids:
                waiter = self.client.get_waiter('instance_terminated')
                waiter.wait(InstanceIds=[instance_id])
                print(f"Instance {instance_id} has been terminated.")
        except Exception as e:
            print(f"Error terminating cluster: {e}")

if __name__ == '__main__':

    
    cluster = HPCCluster(region_name='us-west-2')


    # This is all bad as it needs to be read via yaml file from ~/.cloudmesh/cloudmesh.yaml
    # This is already implemented and we can use methods from cloudmesh-common and cloudmesh-config ...
    # the following is absolutely bad programming practice
    key_name = 'my-key-pair'
    image_id = 'ami-1234'  # Replace with your desired AMI ID
    use_gpu = True  # Set to True if you want GPU instances, False for non-GPU
    security_group_id = 'sg-1234'  # Replace with your security group ID
    instance_count = 3
    
    # cluster.create_key_pair(key_name)
    
    instance_ids = cluster.launch_cluster(image_id, use_gpu, key_name, security_group_id, instance_count)

    # do the work here

    # cluster.terminate_cluster(instance_ids)
