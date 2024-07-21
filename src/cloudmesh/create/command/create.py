from cloudmesh.create.create import Create
from cloudmesh.common.console import Console
from cloudmesh.common.debug import VERBOSE
from cloudmesh.common.parameter import Parameter
from cloudmesh.common.util import banner
from cloudmesh.common.util import path_expand
from cloudmesh.common.variables import Variables
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
                create [--provider=PROVIDER] [--gpus=GPU] [--servers=SERVERS] [--config=CONFIG] --name=NAME
                create list
                
          This command creates a cluster on a given cloud provider. You can either use the commandline 
          arguments to specify the details of the cluster or you can use the yaml file.
          The details of the cluster will be stored in ~/.cloudmesh/clusters.yaml

          Arguments:
              SERVERS   the number of servers to create [default: 1]
              PROVIDER  the cloud provider, AWS, AZURE, GOOGLE [default: AWS]
              GPUS      the number of gpus per server [default: 0]
              CONFIG    a YAML configuration file
              NAME      the name of the cluster

          Options:
              -f      specify the file

          Description:

            > cms create --provider=aws --servers=1 --gpus=1
            >   creates a cluster on aws with 1 server and 1 gpu
            >   the details of the cluster will be addedto a yaml file in the 
            >   ~/.cloudmesh/clusters.yaml 

            > cms create --config=config.yaml
            >   creates a cluster based on the configuration in the yaml file

            > The format of the yamls file is as follows: 
            
            >    cluster:
            >    - name: mycluster-aws
            >      provider: aws
            >      servers: 1
            >      gpus: 1

            > Note that multiple clusters can be specified in the yaml file
            
            Format of the yaml file:

            cluster:
                - name: mycluster-aws
                  provider: aws
                  servers: 1
                  gpus: 1
                - name: mycluster-azure
                  provider: aws
                  servers: 1
                  gpus: 1

            > cms create list
            >   lists the clusters that are available in the ~/.cloudmesh/clusters.yaml
            >   In addition to the definition of the cluster a status is also stored that 
            >   is aquired for the cluster from the cloud provider. THis includes if the cluster 
            >   is running, paused, or terminated. It also includes information such as accounting 
            >   data to show how much the cluster is costing and how long it is running.
            >   Cost data per hour is added.

            Creadentials

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

                We may use the cloudmesh common library for this.


        """

        variables = Variables()
        variables["debug"] = True

        banner("original arguments", color="RED")

        VERBOSE(arguments)

        banner(
            "rewriting arguments so we can use . notation for file, parameter, and experiment",
            color="RED",
        )

        map_parameters(arguments, "file", "parameter", "experiment")

        VERBOSE(arguments)

        banner(
            "rewriting arguments so we convert to appropriate types for easier handling",
            color="RED",
        )

        arguments = Parameter.parse(
            arguments, parameter="expand", experiment="dict", COMMAND="str"
        )

        VERBOSE(arguments)

        banner("showcasing tom simple if parsing based on teh dotdict", color="RED")

        m = Create()

        #
        # It is important to keep the programming here to a minimum and any substantial programming ought
        # to be conducted in a separate class outside the command parameter manipulation. If between the
        # elif statement you have more than 10 lines, you may consider putting it in a class that you import
        # here and have proper methods in that class to handle the functionality. See the Manager class for
        # an example.
        #

        if arguments.file:
            print("option a")
            m.list(path_expand(arguments.file))

        elif arguments.list:
            print("option b")
            m.list("just calling list without parameter")

        Console.error("This is just a sample of an error")
        Console.warning("This is just a sample of a warning")
        Console.info("This is just a sample of an info")

        Console.info(
            " You can witch debugging on and off with 'cms debug on' or 'cms debug off'"
        )

        return ""
