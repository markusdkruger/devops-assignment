# Table of Contents
- [Table of Contents](#table-of-contents)
  - [Introduction](#introduction)
  - [Artifacts](#artifacts)
    - [Python Application](#python-application)
      - [Python Code](#python-code)
      - [Dockerfile](#dockerfile)
    - [Restart Controller](#restart-controller)
      - [Python Code](#python-code-1)
      - [Dockerfile](#dockerfile-1)
    - [Kubernetes Deployment Manifests](#kubernetes-deployment-manifests)
      - [Istio Gateway (If not available yet)](#istio-gateway-if-not-available-yet)
      - [Restart Controller](#restart-controller-1)
      - [Python Application](#python-application-1)
  - [Cluster Adjustments](#cluster-adjustments)

## Introduction


The following was requested as part of the assignment:

* Prepare manifests for two different kubernetes environments test and prod
* These manifests will be rolled out on the same cluster and the same namespace
* Use Kustomize to generate manifests - They should share as much as possible and rely on patches for environment specific configurations
* The manifests must have the following labels set
  * **env** must have values *test* or *prod* 
  * **app** must have value helloworld
* Service is based on a python application that exposes a HTTP GET endpoint, with the response returning content of message stored in ConfigMap
* The service must be accessible from outside the cluster via an Istio Gateway
* Mention any points that will require to be adjusted in different contexts (workstation vs other cluster)
* Design a controller that watches above ConfigMap and do a rolling restart of the service in case of change:

## Artifacts
### Python Application

Simple Python application that exposes 3 HTTP resources:
* **/** - Default resource just returning a HTML header
* **/message** - This resource will return the value of an environment variable **ENV_MESSAGE**
* **/messageFromFile** - This resource will return **MESSAGE** field from a file stored at **/tmp/config.cfg**

#### Python Code
```
import os
from flask import Flask
app = Flask(__name__)

@app.route('/', methods=['GET'])
def home():
    return '''<h1>Default API Route - Devops Assignment Python Application</h1>'''

@app.route('/message', methods=['GET'])
def message():
    return os.environ.get('ENV_MESSAGE', '')

@app.route('/messageFromFile', methods=['GET'])
def messageFromFIle():
    app.config.from_pyfile('/tmp/config.cfg')
    print(os.environ)
    return app.config['MESSAGE']

if __name__ == '__main__':
    app.run(host="0.0.0.0", port=5000)
```
#### Dockerfile
```
FROM alpine:latest
RUN apk update
RUN apk add py-pip
RUN apk add --no-cache python3-dev 
RUN pip install --upgrade pip
WORKDIR /app
COPY . /app
# Default file with MESSAGE field that will be replaced by configMap when deployed to K8
COPY config/config.cfg /tmp/config.cfg
RUN pip --no-cache-dir install -r requirements.txt
CMD ["python3", "hello-world.py"]
```

### Restart Controller

The restart controller is another application written in Python that will be deployed to cluster. The controller must restart the deployments(services) when ConfigMap is updated with a new value

1. The controller is used to watch for events orignating from changes on cluster using the Kubernetes API.
2. If an event is received, which is for change to **Configmap**, and the annotation **rolling.restart.controller/triggerRestart** on ConfigMap is set to *true*, it will trigger the next function responsible for restart.
3. The restart method filters for deployments which contains the same labels for **env** and **app** as the ConfigMap. This is to ensure only apps relating to the same ConfigMap is retrieved.
4. A loop is then done to go through all the filtered deployments
5. If the annotation **rolling.restart.controller/restartOnTrigger** is set to *true* for the deployment, it will process restart for the deployment
6. To restart a deployment, a change is made to current deployment manifest which will trigger the restart by Kubernetes. This is done by adding/updating an annotation **rolling.restart.controller/restartTimestamp** on the deployment.

#### Python Code

```
from kubernetes import client, config, watch
import datetime

def perform_rolling_restart(configMapNamespace, appLabel, envLabel):
    appsAPI = client.AppsV1Api()

    try: 
        print("Perform Rolling Restart Handler")
        
        # Get deployments in same namespace, with matching 'app' and 'env' labels as the ConfigMap
        labelSelector= 'app=' + appLabel + ',env=' + envLabel
        deployments = appsAPI.list_namespaced_deployment(namespace=configMapNamespace,label_selector=labelSelector)
        
        # For each deployment found with above list matchin namespace, app and env
        for deployment in deployments.items:
            print(deployment)
            
            if (deployment.metadata.annotations["rolling.restart.controller/restartOnTrigger"] == 'true'):
                
                print("Annotation is true - Updating restartTimestamp to perform rolling restart")
                
                # Increment the annotation to trigger the rolling update
                timestamp = datetime.datetime.utcnow()
                timestamp = str(timestamp.isoformat("T") + "Z")
                restartAnnotation = {
                    'spec': {
                        'template':{
                            'metadata': {
                                'annotations': {
                                    'rolling.restart.controller/restartTimestamp': timestamp
                                }
                            }
                        }
                    }
                }
                
                # Update the Deployment which will restart the deployment
                appsAPI.patch_namespaced_deployment(deployment.metadata.name, configMapNamespace, restartAnnotation)
            
        print("Completed Rolling Restart Handler")
            
    except Exception as e:
        print(f"Caught an exception in perform_rolling_restart: {e}")
    
def configmap_handler(event):
    try:
        # If object is a Configmap, and annotation for restart (rolling.restart.controller/triggerRestart) is set to true, trigger the restart handler
        if (event['object'].kind == "ConfigMap") and (event['object'].metadata.annotations["rolling.restart.controller/triggerRestart"] == 'true'):
            print("ConfigMap with annotation set to true has changed, triggering rolling restart...")
            perform_rolling_restart(event['object'].metadata.namespace, event['object'].metadata.labels['app'], event['object'].metadata.labels['env'])
            
    except Exception as e:
        print(f"Caught an exception in configmap_handler: {e}")

def main():
    config.load_incluster_config()
    coreAPI = client.CoreV1Api()
    watcher = watch.Watch()

    for event in watcher.stream(coreAPI.list_config_map_for_all_namespaces):
        configmap_handler(event)

if __name__ == "__main__":
    main()
```

#### Dockerfile
```
FROM alpine:latest
RUN apk update
RUN apk add py-pip
RUN apk add --no-cache python3-dev 
RUN pip install --upgrade pip
WORKDIR /app
COPY . /app
RUN pip --no-cache-dir install -r requirements.txt
CMD ["python3", "rolling_restart_controller.py"]
```

### Kubernetes Deployment Manifests

This section will provide steps to deploy the application to Kubernetes cluster.
It is assumed that kubeconfig is already in place for CLI to interact with Kubernetes API, and context is set to the appropriate cluster and namespace where application must be deployed to

For all steps listed, command line should be opened at **$REPO_LOCATION/deployment**

#### Istio Gateway (If not available yet)

To deploy Istio Gateway, the following command can be used:
```
kubectl apply -f istio-gateway.yaml
```

#### Restart Controller ####

To deploy the restart controller, the following command can be used:
```
kubectl apply -f controller/restart-controller-deployment.yaml
```

#### Python Application

To deploy the application that was created, the following commands can be used depending on the environment.
The commands below is one-liner to apply Kustomize to base, and deploy to the Kubernetes cluster
* **test**
```
kustomize build python-app/overlays/test | kubectl apply -f -
```
* **prod**
```
kustomize build python-app/overlays/prod | kubectl apply -f -

```

## Cluster Adjustments 

The above components can be deployed to a workstation or other remote clusters. This will however require the following to be done to enable the deployment.

* kubectl must be set to use the correct context before any of the kubectl commands above are executed to apply configurations to cluster. This can be done by using the following command, and setting **MY_CLUSTER_NAME** accordginly to context existing in kubeconfig
  ```
  kubectl config use-context $MY_CLUSTER_NAME 
  ```
* If airgapped environments exists, or limited access to public registries is available from clusters, the docker images used in deployments will need to change to use private registries to which the cluster has acecss. The images used for this deployment will need to be pushed to these registries. If registry requires authentication, this will also require **imagePullSecrets** to be added to deployment specs.
* If cluster has strict RBAC policies, **ServiceAccounts** will require appropriate **role**, **clusterrole**, **rolebinding** and/or **clusterrolebinding** to be setup
* For the assignment on workstation, hosts file was used for DNS resolution to ***.devopsassignment.com** to forward traffic to Istio Ingress Gateway. As this is fictitious DNS, the hosts used on **VirtualServices** will need to be updated to use DNS avaialble.
* For assignment, it is assumed to Istio Gateway is already configured for cluster - If not, Istio Ingress Gateway will need to be deployed to cluster.
