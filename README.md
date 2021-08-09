# Introdução 
O Objetivo dessa aplicação é remover as imagens antigas dos repositórios do registry, baseando-se numa lista e em regex baseadas no nome da tag

# Como usar
Configurar a aplicação por meio do arquivo config.yaml com as seguintes chaves:

Endereço do Registry:
'''
registry:
  address: "https://meuregistry.azurecr.io"
'''

Indica se a execução deve deletar as imagens de fato eu se é apenas um teste
'''
dry_run: false
'''

Indica se as imagens que não forem compatíveis com nenhum padrão devem ser excluídas ou não
'''
delete_others: true
'''

Padrões para deleção, "regex" indica a regex que faz match com o nome da tag, "howManyToKeep" quantas imagens desse padrão devem ser mantidas considerando as mais recentes.
'''
tagsGroups:
  build:
    regex: ".*build$"
    howManyToKeep: 10      
  dev:
    regex: ".*dsv$"
    howManyToKeep: 3    
  hml:
    regex: ".*hml$"
    howManyToKeep: 3      
  prd:
    regex: ".*prd$"
    howManyToKeep: 3     
'''

Lista de repositorios a serem processados
'''
repository:
  - "repo.one"
  - "repo.two"
'''