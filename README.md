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


* https://github.com/cloudmesh/cloudmesh.cmd5

## Installation

Cloudmesh craete can be installed with 

```bash
pip install cloudmesh-create
```

## Source code 

The source code is located at

* <https://github.com/cloudmesh/create>

If you download it and make modifications as developer, it can be installed with 

```bash
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
    create [--provider=PROVIDER] [--gpus=GPU] [--servers=SERVERS] [--config=CONFIG] --name=NAME
    create info [--name=NAME]

  This command creates a cluster on a given cloud provider. You can 
  either use the commandline arguments to specify the details of the 
  cluster or you can use the yaml file. The details of the cluster 
  are be stored in .cloudmesh/clusters.yaml

  Arguments:
    SERVERS   the number of servers to create [default: 1]
    PROVIDER  the cloud provider, AWS, AZURE, GOOGLE [default: AWS]
    GPUS      the number of gpus per server [default: 0]
    CONFIG    a YAML configuration file
    NAME      the name of the cluster

  Options:
    --provider=PROVIDER  the cloud provider, AWS, AZURE, GOOGLE [default: AWS]
    --gpus=GPU           the number of gpus per server [default: 0]
    --servers=SERVERS    the number of servers to create [default: 1]
    --config=CONFIG      a YAML configuration file
    --name=NAME          the name of the cluster

  Description:

  > cms create --provider=aws --servers=1 --gpus=1
  >   creates a cluster on aws with 1 server and 1 gpu
  >   the details of the cluster will be addedto a yaml file in the 
  >   ~/.cloudmesh/clusters.yaml 
  >
  > cms create --config=config.yaml
  >   creates a cluster based on the configuration in the yaml file
  >
  > The format of the yamls file is as follows: 
  >
  >    cluster:
  >    - name: mycluster-aws
  >      provider: aws
  >      servers: 1
  >      gpus: 1
  >
  > Note that multiple clusters can be specified in the yaml file
  >
  > Format of the yaml file:
  >
  > cluster:
  >    - name: mycluster-aws
  >      provider: aws
  >      servers: 1
  >      gpus: 1
  >    - name: mycluster-azure
  >      provider: aws
  >      servers: 1
  >      gpus: 1
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

```
<!-- STOP-MANUAL -->