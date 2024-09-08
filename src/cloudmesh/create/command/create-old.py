from cloudmesh.common.console import Console
from cloudmesh.common.debug import VERBOSE
from cloudmesh.common.parameter import Parameter
from cloudmesh.common.util import banner
from cloudmesh.common.util import path_expand
from cloudmesh.common.variables import Variables
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
            create [--provider=PROVIDER] [--kind=CLUSTERTYPE] [--gpus=GPU] [--nodes=NODES] [--config=CONFIG] --name=NAME
            create info [--name=NAME]
                
          This command creates a cluster on a given cloud provider. You can 
          either use the commandline arguments to specify the details of the 
          cluster or you can use the yaml file. The details of the cluster 
          are be stored in .cloudmesh/clusters.yaml

          Arguments:
            NODES     the number of nodes to create [default: 1]
            PROVIDER  the cloud provider, aws, azure, google [default: aws]
            GPUS      the number of gpus per server [default: 0]
            CONFIG    a YAML configuration file [default: ./cloudmesh.yaml]
            NAME      the name of the cluster [deafault: cluster]
            KIND      the kind of the cluster [default: kubernetes]

          Options:
            --provider=PROVIDER  the cloud provider, aws, azure, google [default: aws]
            --gpus=GPU           the number of gpus per server [default: 0]
            --servers=SERVERS    the number of servers to create [default: 1]
            --config=CONFIG      a YAML configuration file
            --name=NAME          the name of the cluster
            --kind=CLUSTERTYPE   the kind of cluster. Values are kubernetes, slurm [default: kubernetes]

          Description:

          > cms create --provider=aws --servers=1 --gpus=1 --name=eks-cluster
          >   creates a cluster on aws with 1 server and 1 gpu
          >   the details of the cluster will be addedto a yaml file in the 
          >   ~/.cloudmesh/clusters.yaml 
          >
          > cms create --config=config.yaml
          >   creates a cluster based on the configuration in the yaml file
          >
          > The format of the yaml file is as follows:
          >
          > cloudmesh:
          >  cluster:
          >    aws:
          >      - name: cluster-1
          >        nodegroups:
          >          - name: workers
          >            instanceType: t2.micro # instance type
          >            desiredCapacity: 2     # number of nodes
          >            volumeSize: 20         # min size in GB
          >            capacityType: 'SPOT'   # SPOT or ON_DEMAND
          >
          > Note that multiple clusters can be specified in the yaml file
          >
          > Format of the yaml file:
          >
          > cloudmesh:
          >  cluster:
          >    aws:
          >      - name: cluster-1
          >        nodegroups:
          >          - name: workers
          >            instanceType: t2.micro # instance type
          >            desiredCapacity: 2     # number of nodes
          >            volumeSize: 20         # min size in GB
          >            capacityType: 'SPOT'   # SPOT or ON_DEMAND
          >      - name: cluster-2
          >        nodegroups:
          >          - name: workers
          >            instanceType: t2.large # instance type
          >            desiredCapacity: 10     # number of nodes
          >            volumeSize: 20         # min size in GB
          >            capacityType: 'SPOT'   # SPOT or ON_DEMAND
          >
          > cms create info
          >   lists the clusters that are available in the ~/.cloudmesh/clusters.yaml
          >   In addition to the definition of the cluster a status is also stored that 
          >   is aquired for the cluster from the cloud provider. THis includes if the cluster 
          >   is running, paused, or terminated. It also includes information such as accounting 
          >   data to show how much the cluster is costing and how long it is running.
          >   Cost data per hour is added.
          >
          > Creadentials
          > 
          >    credential management is critical for the cloud and can be obtained through 
          >    the .cloudmesh/cloudmesh.yaml file.
          >
          >    I forgot how to use it so we may want to look up the format in mor detail 
          >    and adapt accordingly.
          >
          >    We can also use another method .. one that would come with the provider recommendation.
          >
          >    Our requirements include
          >
          >    1. the credentials must not be stored in the git repo so that accidential checkins are avoided.
          >    2. the credentials must be stored in a secure way in ~/.cloudmesh/cloudmesh.yaml or another file in that directory.
          >    3. ~/.cloudmesh must be set to read only for the user
          >    4. the credentials must be encrypted.
          >    5. the credentials must be decrypted on the fly when they are used
          >    6. any code we write as example must not have the credentials hardcoded in the code or suggest to
          >       do so.

          > We may use the cloudmesh common library for credential maangement.

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

        #arguments = Parameter.parse(
        #    arguments, parameter="expand", experiment="dict", COMMAND="str"
        #)


        arguments.provider = arguments.provider.lower()


        arguments.kind = arguments.kind or "kubernetes"
        arguments.config = path_expand("./config.yaml")


        arguments.dryrun = dryrun = True


        variables = Variables()
        variables["debug"] = True


        if arguments.provider == 'aws' and arguments.kind == "kubernetes":
            from cloudmesh.create.aws.create_kubernetes_cluster import deploy_cluster
            cluster = deploy_cluster(config=arguments.config)
        else:
            Console.error("This cluser provider and kind are not yet supported")
            return ""



        if arguments.info:
            Console.ok("calling info")

            cluster.info(arguments.name, detail=True, dryrun=True)

        # cluster.list("just calling list without parameter")
        elif arguments.create:
            print("calling create")
            #cluster.create(arguments.name, detail=True)

        return ""
