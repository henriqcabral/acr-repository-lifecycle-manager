from azure.identity import AzureCliCredential
from azure.containerregistry import ContainerRegistryClient
from azure.containerregistry import TagOrder
from Repository import Repository as Repository
from time import perf_counter
import logging
import logging.config
import yaml

def set_config_file(config_filename):
    try:
        with open(config_filename) as f:
            config = yaml.load(f, Loader=yaml.FullLoader)
    except FileNotFoundError:
        raise Exception("config.yaml file must exist.")

    if not("registry" in config):
        raise Exception("registry address must be set at configuration file.")
    else:
        if not("address" in config["registry"]):
            raise Exception("registry address must be set at configuration file.")
        
    if not("repository" in config):
        raise Exception("At least one repository in repository key must be set at configuration file.")
    
    if not("tagsGroups" in config):
        print("If no tags_groups are informed images will not be purged.")

    if not("tagsGroups" in config):
        config["tagsGroups"] = dict()

    if not("dry_run" in config):
        config["dry_run"] = False
    
    if not("delete_others" in config):
        config["delete_others"] = False

    if not("log_file" in config):
        config["log_file"] = 'logging.yaml' 
    
    return config

def set_logger(log_filename):
    with open(log_filename) as log_filehandler:
        log_config = yaml.load(log_filehandler, Loader=yaml.FullLoader)

    logging.config.dictConfig(config=log_config)

    file = logging.getLogger('arlmLogger')
    console = logging.getLogger('consoleLogger')

    return file, console

def main():
    #### Load Config and Logger
    config = set_config_file(config_filename='config.yaml')
    logger_file, logger_console = set_logger(log_filename=config["log_file"])

    #### Initialize Client
    client = ContainerRegistryClient(endpoint=config["registry"]["address"],credential=AzureCliCredential())

    #### Main Cleaning looping
    tag_order = TagOrder.LAST_UPDATE_TIME_DESCENDING

    total_deleted_tags=0
    total_deleted_manifests=0
    
    for repository_name in config["repository"]:   
        t0 = perf_counter()  
      
        repository = Repository( 
            client=client,
            name=repository_name, 
            groups=config["tagsGroups"], 
            logger=logger_file
        )

        tag_list = client.list_tag_properties(repository=repository.name, order_by=tag_order)
    
        elapsed_time_sorting = repository.sort_tags(tag_list=tag_list)
        elapsed_time_flagging = repository.flag_tags_to_delete(delete_others=config["delete_others"])
        elapsed_time_deleting_tags = repository.delete_flagged_tags(dry_run=config["dry_run"])
        elapsed_time_deleting_manifests = repository.delete_orphaned_manifests(dry_run=config["dry_run"])        

        t1 = perf_counter()  
        elapsed_time = t1 - t0

        total_deleted_tags += repository.deleted_tags
        total_deleted_manifests += repository.deleted_manifests

        logger_console.info("%s -> %.2fs Deleting %i Tags | %.2fs Deleting %i Manifests | %.2fs Total Elapsed Time ",
            repository.name,
            elapsed_time_deleting_tags,
            repository.deleted_tags,
            elapsed_time_deleting_manifests,
            repository.deleted_manifests,
            elapsed_time)

    logger_console.info("%i Tags Deleted Total | %i Manifests Deleted Total", total_deleted_tags, total_deleted_manifests)

if __name__ == "__main__":
    main()