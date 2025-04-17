from dataclasses import dataclass, field, replace
from tree_sitter import Node
from pathlib import Path
from typing import Dict, Iterable, Any, List


@dataclass
class Method():
    name:str
    params:list[str] = field(default_factory=list)
    retour:list[str] = field(default_factory=list)

    def addReturn(self,returnType)->'Method':
        if returnType in self.retour:
            return self
        return replace(self, retour=self.retour + [returnType])
    
    def addParam(self, param:str)->'Method':
        return replace(self, self.params + [param])

@dataclass
class Instance():
    name:str
    type:type

@dataclass
class File():
    name:str
    path:str
    dependancie_name:str
    code:str

@dataclass
class Class():
    class_type:str
    path:Path
    name:str
    code: str
    node: Node
    method: Iterable["Method"] = field(default_factory=list)
    instance: Iterable["Instance"] = field(default_factory=list)
    children: Iterable["str"] = field(default_factory=list)
    params: Iterable["str"] = field(default_factory=list)
    retour: Iterable["str"] = field(default_factory=list) 
    instanciation_class: Dict[str,str] = field(default_factory=dict) # allow to find dependency

    @classmethod
    def register(cls, node:Node,link:Path, code:str)->'Class': # type: ignore
        name = ''
        name_node = node.child_by_field_name("name")
        if name_node:
            name = code[name_node.start_byte:name_node.end_byte].decode("utf-8")
        return Class(
            class_type=node.type,
            path=link,
            name=name,
            code=code,
            node=node,
        )

    def addMethod(self, name:Node, params: Node | None, retour: Node | None, method:Method|None)->'Class':
        if not method : 
            nameString = self.code[name.start_byte:name.end_byte].decode("utf-8")
            paramsString = self.code[params.start_byte:params.end_byte].decode("utf-8")if params else ""
            retourString = self.code[retour.start_byte:retour.end_byte].decode("utf-8")if retour else ""
            method = Method(name=nameString, params=[paramsString], retour=[retourString])
        return replace(self,method=self.method + [method])
    
    def addInstance(self,name:Node, type:Node)->'Class':
        nameString = self.code[name.start_byte:name.end_byte].decode("utf-8")
        typeString = self.code[type.start_byte:type.end_byte].decode("utf-8")
        instance = Instance(name=nameString, type=typeString)
        return replace(self,instance=self.instance + [instance])
    
    def addDependencies(self, dependencies:List)->'Class':
        return replace(self,children=dependencies)

    def addInstanciation_class(self, instanciation_class:dict)->'Class':
        return replace(self,instanciation_class=instanciation_class)
    
    def registerNode(self,node:Node)->'Class':
        return replace(self,node=node)
    

@dataclass
class Project():
    name: str
    classs : Iterable[Class]
    path:Path

    def addClasses(self,classes:Iterable[Class])->'Project':
        return replace(self,classs=self.classs+classes)
