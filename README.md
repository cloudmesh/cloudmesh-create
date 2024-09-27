# Cloudmesh Command create

[![GitHub Repo](https://img.shields.io/badge/github-repo-green.svg)](https://github.com/cloudmesh/cloudmesh-create)
[![image](https://img.shields.io/pypi/pyversions/cloudmesh-create.svg)](https://pypi.org/project/cloudmesh-create)
[![image](https://img.shields.io/pypi/v/cloudmesh-create.svg)](https://pypi.org/project/cloudmesh-create/)
[![License](https://img.shields.io/badge/License-Apache%202.0-blue.svg)](https://opensource.org/licenses/Apache-2.0)

[![General badge](https://img.shields.io/badge/Status-Production-<COLOR>.svg)](https://shields.io/)
[![GitHub issues](https://img.shields.io/github/issues/cloudmesh/cloudmesh-create.svg)](https://github.com/cloudmesh/cloudmesh-create/issues)
[![Contributors](https://img.shields.io/github/contributors/cloudmesh/cloudmesh-create.svg)](https://github.com/cloudmesh/cloudmesh-create/graphs/contributors)
[![General badge](https://img.shields.io/badge/Other-repos-<COLOR>.svg)](https://github.com/cloudmesh/cloudmesh)


[![Linux](https://img.shields.io/badge/OS-Linux-orange.svg)](https://www.linux.org/)
[![macOS](https://img.shields.io/badge/OS-macOS-lightgrey.svg)](https://www.apple.com/macos)
[![Windows](https://img.shields.io/badge/OS-Windows-blue.svg)](https://www.microsoft.com/windows)

Status: This cloudmesh module is not yet working and is only a draft.

## Installation

Note: pip install is not yet working, please use source install

Cloudmesh craete can be installed with  

```bash
pip install cloudmesh-create
```

## Source code 

The source code is located at

* <https://github.com/cloudmesh/create>

If you download it and make modifications as developer, it can be installed with 

```bash
# set up general cloudmesh
pip install cloudmesh-common
pip install cloudmesh-vpn
pip install cloudmesh-ee

# set up create from source
git clone https://github.com/cloudmesh/cloudmesh-create.git
cd create
pip install - e .
```

## Manual page in the README.md

To create the manual page  you must also check out cloudmesh-common next to cloudmesh-create.

To modify the manual page in this readme, edit the code and call. 

```bash
make readme
```

The code is located in 

* cloudmesh/create/command/create.py

~

## Manual Page

<!-- START-MANUAL -->
```
Command create
==============

::

Usage:
            create [--provider=PROVIDER] [--kind=CLUSTERTYPE] [--gpus=GPU] [--nodes=NODES] [--config=CONFIG] [--dryrun] --name=NAME
            create [--config=CONFIG] [--dryrun] --name=NAME
            create info [--name=NAME] [--config=CONFIG] [--local | --remote] [--sync] [--dryrun]
            create delete [--kind=CLUSTERTYPE] [--name=NAME] [--dryrun]
            create run [--name=NAME] [--script=SCRIPT] [--dryrun]
            create uploadkey [--name=NAME] [--path=PATH] [--dryrun]


          This command creates a cluster on a given cloud provider. You can 
          either use the commandline arguments to specify the details of the 
          cluster or you can use the yaml file. The details of the cluster 
          are be stored in .cloudmesh/clusters.yaml

          Arguments:
            NODES     the number of nodes to create [default: 1]
            PROVIDER  the cloud provider, aws, azure, google [default: aws]
            GPUS      the number of gpus per server [default: 0]
            CONFIG    a YAML configuration file [default: ./cloudmesh.yaml]
            NAME      the name of the cluster [default: cluster]
            KIND      the kind of the cluster [default: PCS]
            PATH      the path to the key file [default: ~/.ssh/id_rsa.pub]
            SCRIPT    the script to run on the cluster

          Options:
            --provider=PROVIDER  the cloud provider, aws, azure, google [default: aws]
            --gpus=GPU           the number of gpus per server [default: 0]
            --servers=SERVERS    the number of servers to create [default: 1]
            --config=CONFIG      a YAML configuration file
            --name=NAME          the name of the cluster
            --script=SCRIPT      the script to run on the cluster
            --kind=CLUSTERTYPE   the kind of cluster. Values are kubernetes, slurm [default: PCS]
            --dryrun             specify if you just want to dryrun the command
            --source             the source of the cluster info, local or remote [default: local]
            --sync               update the cluster info in the yaml file

  Pre-requisites:
    - A default vpc
    - atleast two public subnets
    - although no manual steps are required to be performed, user should have access to IAM to create policies, role, instance profile.
    
  Description:
    cms create command can create multiple types of clusters; currently AWS Parallel Computing Service (PCS) or Elastic Kubernetes Service (EKS)
  
    For AWS Parallel Computing Service (PCS) a simple command looks like this;
    cms create --name=pcs001
    

    This creates a cluster by reading the config.yaml file from the current directory, creates all required pre-requisite resources 
    if they are not already created. 
    Then creates the cluster, followed worker node groups as specified in the config.yaml file and finally creates a queue.

    A login node or a head node is also created for every cluster. A head node is what you can use to submit slurm jobs to the cluster.

    If you do not want to use a config file, you could also provide inputs to the "create" command such as;
    
    cms create --provider=aws --servers=1 --gpus=1 

      creates a cluster on aws with 1 server and 1 gpu
      the details of the cluster will be added to a yaml file in the 
      ~/.cloudmesh/clusters.yaml 
   
    cms create --name=pcs001 --config=config.yaml
      creates a cluster based on the configuration in the yaml file
   
    The format of the yamls file is as follows: 
   
    cloudmesh:
      cluster:
        aws:
          kind: PCS #| kubernetes
          size: SMALL #| MEDIUM | LARGE | XLARGE | CUSTOM
          nodegroups:
            - name: workers01
              instanceType: t2.micro # instance type
              desiredCapacity: 1 # number of nodes
              volumeSize: 128 #min size for EKS 20 GB, for PCS 128 GB
              capacityType: 'SPOT' # SPOT or ONDEMAND

    Note that multiple clusters or nodegroups can be specified in the yaml file
  
   
    cms create info
      lists the clusters that are available in the ~/.cloudmesh/clusters.yaml
      In addition to the definition of the cluster a status is also stored that 
      is aquired for the cluster from the cloud provider. This includes if the cluster 
      is running, paused, or terminated. It also includes information such as accounting 
      data to show how much the cluster is costing and how long it is running.
      Cost data per hour is added.
      info command, by default pulls info from the local file, while running info, you can specify an additional 
      "update" flag"

      Some examples of info command;

      cms create info --name=pcs001 -  reads the info from local yaml file 
      cms create info --name=pcs001 --local -  reads the info from local yaml file and present the cluster info
      cms create info --name=pcs001 --update -  syncs information between Cloud provider and local yaml file 
      cms create info --name=pcs001 --remote -  syncs information between Cloud provider and local yaml file

    cms create delete
      delete the cluster and its associated resources such as nodegroups, nodes, queues.
      --name - Cluster name is the mandatory parameter
      similar to other commands, default clustertype for delete is "PCS" so if you would like to delete an EKS 
      cluster you will have to specify it.

      Some examples of info command;

      cms create delete --name=pcs001 -  deletes the PCS cluster named pcs001
      cms create delete --name=eks001 --kind=EKS -  deletes the EKS cluster named eks001

    cms create run
    
      In case of PCS clusters, run command allows you to run a shell script or a python script on the head node of the cluster
      You can also submit a slurm job using the run option.


      In case of EKS clusters, the run command many not be very useful as you would interact with the cluster using kubectl commands.
      And since the cluster creation process updates the local kube config file, you should be able to run kubectl commands right away.

      Some examples of run command;

      cms create run --name=pcs001 --script='install.sh'  
      cms create run --name=pcs001 --script='/home/user/slurmjob.sh'  
      
    cms create uploadkey
    
      uploadkey applies only to PCS clusters. Using uploadkey function you can exchange ssh keys between the current user and the 
      head node of the PCS cluster.
      Once keys are exchanged, you can login to head node and interact with the cluster using slurm scheduler or submit slurm jobs.

      Some examples of run command;

      cms create uploadkey --name=pcs001  

   
    Credentials
       
       credential management is critical for the cloud and can be obtained through 
       the .cloudmesh/cloudmesh.yaml file.
   
       I forgot how to use it so we may want to look up the format in mor detail 
       and adapt accordingly.
   
       We can also use another method .. one that would come with the provider recommendation.
   
       Our requirements include
   
       1. the credentials must not be stored in the git repo so that accidential checkins are avoided.
       2. the credentials must be stored in a secure way in ~/.cloudmesh/cloudmesh.yaml or another file in that directory.
       3. ~/.cloudmesh must be set to read only for the user
       4. the credentials must be encrypted.
       5. the credentials must be decrypted on the fly when they are used
       6. any code we write as example must not have the credentials hardcoded in the code or suggest to
          do so.


```
<!-- STOP-MANUAL -->
