from cloudmesh.common.console import Console
from cloudmesh.common.debug import VERBOSE
from cloudmesh.common.parameter import Parameter
from cloudmesh.common.util import banner
from cloudmesh.common.util import path_expand
from cloudmesh.common.variables import Variables
from cloudmesh.common.FlatDict import FlatDict
from torchgen.api.python import arg_parser_unpack_method
from torchgen.executorch.api.et_cpp import arguments

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
            create info [--name=NAME] [--config=CONFIG] [--dryrun]
                
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
            KIND      the kind of the cluster [default: kubernetes]

          Options:
            --provider=PROVIDER  the cloud provider, aws, azure, google [default: aws]
            --gpus=GPU           the number of gpus per server [default: 0]
            --servers=SERVERS    the number of servers to create [default: 1]
            --config=CONFIG      a YAML configuration file
            --name=NAME          the name of the cluster
            --kind=CLUSTERTYPE   the kind of cluster. Values are kubernetes, slurm [default: kubernetes]
            --dryrun             specify if you just want to dryrun the command
        """


        map_parameters(arguments, 
                       "provider",
                       "gpus",
                       "servers",
                       "dryrun",
                       "config",
                       "kind",
                       "name")
        VERBOSE(arguments)
        variables = Variables()
        variables["debug"] = True

        #arguments = Parameter.parse(
        #    arguments, parameter="expand", experiment="dict", COMMAND="str"
        #)


        arguments.provider = arguments.provider.lower()


        arguments.kind = arguments.kind or "kubernetes"
        arguments.config = path_expand("./config.yaml")



        if arguments.provider == 'aws' and arguments.kind == "kubernetes":
            from cloudmesh.create.aws.create_kubernetes_cluster import deploy_cluster
            cluster = deploy_cluster(config=arguments.config, dryrun=arguments.dryrun)
        else:
            Console.error("This cluser provider and kind are not yet supported")
            return ""



        if arguments.info:
            Console.ok("calling info")

            cluster.info(name=arguments.name, detail=True, dryrun=True)

        # cluster.list("just calling list without parameter")
        elif arguments.create:
            print("calling create")
            cluster.setup()
            cluster.create(name=arguments.name, detail=True, dryrun=arguments.dryrun)

        return ""
