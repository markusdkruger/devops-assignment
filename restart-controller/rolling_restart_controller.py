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