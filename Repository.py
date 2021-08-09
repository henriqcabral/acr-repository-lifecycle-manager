import re
import concurrent.futures
from azure.containerregistry import ContainerRegistryClient
from time import perf_counter

class Repository:
    def __init__(self, client, name, groups, logger):
        self.__client = client
        self.__name = name
        self.__groups = groups
        self.__sorted_tags = {"others": list()}
        self.__logger = logger
        self.__deleted_tags = 0
        self.__deleted_manifests = 0

    @property
    def deleted_tags(self):
        return self.__deleted_tags

    @property
    def deleted_manifests(self):
        return self.__deleted_manifests

    @property
    def name(self):
        return self.__name

    def sort_tags(self, tag_list):
        t0 = perf_counter()   
        ### Initializing Sorted List
        for group_name in self.__groups.keys():
            self.__sorted_tags[group_name] = list()

        ### Sorting tags based on groups
        for tag in tag_list:
            tag_property = self.__parse_tag(tag)
            tag_name = tag_property["name"]
            
            self.__sorted_tags["others"].append(tag_property)
            for group_name in self.__groups.keys():
                group_regex = self.__groups[group_name]["regex"]
            
                match = re.search(group_regex, tag_name)

                if match:
                    self.__sorted_tags[group_name].append(tag_property)
                    self.__sorted_tags["others"].remove(tag_property)
 
        t1 = perf_counter()
        elapsed_time = t1 - t0

        return elapsed_time

    def flag_tags_to_delete(self, delete_others):
        t0 = perf_counter()   
        if delete_others:
            for tag in self.__sorted_tags["others"]:
                tag["delete"] = True


        for group_name in self.__groups.keys():
            group_how_many_to_keep = self.__groups[group_name]["howManyToKeep"]
            sorted_tags_len = len(self.__sorted_tags[group_name])
            how_many_to_keep = group_how_many_to_keep if group_how_many_to_keep <= sorted_tags_len else sorted_tags_len

            for tag in self.__sorted_tags[group_name]:
                idx = self.__sorted_tags[group_name].index(tag) + 1

                if idx > how_many_to_keep:
                    tag["delete"] = True
        
        t1 = perf_counter()
        elapsed_time = t1 - t0
        
        return elapsed_time                    

    def delete_tag(self, dry_run, digest, tag):
        success = True
        try: 
            if dry_run:
                self.__client.get_tag_properties(self.__name, tag=tag)
            else:
                self.__client.delete_tag(self.__name, tag=tag)
            
            self.__deleted_tags+=1

        except Exception as exc:
            exception_type = type(exc).__name__
            self.__logger.info("Exception type %s occurred", exception_type)
            success = False

        tag_data = {"name": tag, "digest": digest}
        return success, tag_data

    def delete_manifest(self, dry_run, manifest_digest):
        success = True
        try:
            if dry_run:
                self.__client.get_manifest_properties(self.__name, tag_or_digest=manifest_digest)
            else:
                self.__client.delete_manifest(self.__name, tag_or_digest=manifest_digest )
            
            self.__deleted_manifests+=1

        except Exception as exc:
            exception_type = type(exc).__name__
            self.__logger.info("Exception type %s occurred", exception_type)
            success = False

        return success, manifest_digest

    def delete_flagged_tags(self, dry_run=False):
        t0 = perf_counter()   

        for group_name in self.__sorted_tags.keys():
            with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
                futures = []
                for tag in self.__sorted_tags[group_name]:
                    
                    name = tag["name"]
                    digest = tag["digest"]
                    delete_tag = tag["delete"]
                    
                    if delete_tag:
                        futures.append(executor.submit(self.delete_tag, dry_run=dry_run, digest=digest, tag=name))
                    else:
                        self.__logger.info("Keeped tag %s with digest %s on %s repository, based on group %s filters" , name, digest, self.__name, group_name)

                for future in concurrent.futures.as_completed(futures):
                    success, tag = future.result()
                    if success:
                        self.__logger.info("Deleted tag %s with digest %s from %s repository, based on group %s filters", tag["name"], tag["digest"], self.__name, group_name)
                    else:
                        self.__logger.warn("Problems deleting tag %s with digest %s from %s repository, based on group %s filters", tag["name"], tag["digest"], self.__name, group_name)
        
        t1 = perf_counter()
        elapsed_time = t1 - t0
        
        return elapsed_time

    def delete_orphaned_manifests(self, dry_run=False):
        t0 = perf_counter()   

        manifest_properties = self.__client.list_manifest_properties(self.__name)            

        with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
            futures = []
            try: 
                for manifest in manifest_properties:
                    if not(manifest.tags):
                        futures.append(executor.submit(self.delete_manifest, dry_run=dry_run, manifest_digest=manifest.digest))
                
                for future in concurrent.futures.as_completed(futures):
                    success, manifest = future.result()
                    if success:
                        self.__logger.info("Manifest %s has no tags and will be definitively deleted from %s", manifest, self.__name)
                    else:
                        self.__logger.info("Problems deleting manifest %s in %s" , manifest_digest, self.__name)
            except:
                self.__logger.warn("Problems deleting orphaned manifests for repository %s", self.__name)


        t1 = perf_counter()
        elapsed_time = t1 - t0
        
        return elapsed_time

    def __parse_tag(self, tag):
        tag_property = dict()
        tag_property["name"] = tag.name
        tag_property["can_delete"] = tag.can_delete
        tag_property["created_on"] = tag.created_on
        tag_property["digest"] = tag.digest
        tag_property["last_updated_on"] = tag.last_updated_on
        tag_property["delete"] = False
        return tag_property