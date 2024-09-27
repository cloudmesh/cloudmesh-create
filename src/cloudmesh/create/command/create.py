from cloudmesh.common.console import Console
from cloudmesh.common.debug import VERBOSE
from cloudmesh.common.parameter import Parameter
from cloudmesh.common.util import banner
from cloudmesh.common.util import path_expand
from cloudmesh.common.variables import Variables
from cloudmesh.common.FlatDict import FlatDict

from cloudmesh.shell.command import PluginCommand
from cloudmesh.shell.command import command
from cloudmesh.shell.command import map_parameters

class CreateCommand(PluginCommand):
    # noinspection PyUnusedLocal
    @command
    def do_create(self, args, arguments):
        """
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
        """

        map_parameters(arguments, 
                       "provider",
                       "gpus",
                       "servers",
                       "dryrun",
                       "config",
                       "kind",
                       "name",
                       "script",
                       )
        VERBOSE(arguments)
        variables = Variables()
        variables["debug"] = True


        arguments.provider = arguments.provider.lower()


        arguments.kind = arguments.kind or "PCS"
        arguments.config = path_expand("./config.yaml")


        #VERBOSE(arguments)

        
        if arguments.provider == 'aws' and arguments.kind == "kubernetes":
          if arguments.info:
             from cloudmesh.create.provider.create_kubernetes import Cluster
             Console.ok("calling EKS Info")
             try:
              info = Cluster.info(name=arguments.name, dryrun=arguments.dryrun)
              print(info)
             except Exception as e:
              print(e)
          elif arguments.delete:
              try:
                from cloudmesh.create.provider.create_kubernetes import Cluster
                Console.ok("calling EKS delete")
                deleteStatus = Cluster.delete('', name=arguments.name, dryrun=arguments.dryrun)
                print(deleteStatus)
              except Exception as e:
                print(e)
                return ""
          elif arguments.run:
             print("calling EKS run")
          elif arguments.uploadkey:
             print("uploadkey function not supported for EKS")
          else: 
             print("calling EKS create")
             from cloudmesh.create.provider.create_kubernetes import Cluster
             try:
               cluster = Cluster(config=arguments.config, cluster_name=arguments.name, dryrun=arguments.dryrun)                           
             except Exception as e:
               print(e)
             #return ""
        elif arguments.provider == 'aws' and arguments.kind == "PCS":
             from cloudmesh.create.provider.create_parallel_cluster import Cluster
             import os
             if arguments.info:
                Console.ok("calling PCS Info")
                try:
                  Clusterinfo = Cluster.info(name=arguments.name, source=arguments.source, update=arguments.sync, dryrun=arguments.dryrun)
                  print(Clusterinfo)
                except Exception as e:
                  print(e)
             elif arguments.delete:
                Console.ok("calling PCS Delete")
                try:
                  Cluster.delete('', name=arguments.name, dryrun=arguments.dryrun)
                except Exception as e:
                  print(e)
             elif arguments.run:
                Console.ok("calling PCS run")
                try:
                  Cluster.run(cluster_name=arguments.name, port=22, rwd='/home/ec2-user/', scriptname=arguments.script, dryrun=arguments.dryrun)
                except Exception as e:
                  print(e)
             elif arguments.uploadkey:
                Console.ok("calling PCS uploadkey")
                try:
                  Cluster.uploadkey(cluster_name=arguments.name, port=22, dryrun=arguments.dryrun)
                except Exception as e:
                  print(e)
             else:
                from cloudmesh.create.provider.create_parallel_cluster import Cluster
                Console.ok("calling PCS create")
                try:
                  cluster = Cluster(config=arguments.config, cluster_name=arguments.name, dryrun=arguments.dryrun)
                  print(type(cluster))
                except Exception as e:
                  print(e)
        else:
          Console.error("This cluser provider and kind are not yet supported")
          return ""
