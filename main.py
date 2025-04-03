from dataclasses import dataclass, field, replace
import os
import sys
from pathlib import Path
from typing import Iterable, Any
from tree_sitter import Language, Parser
import tree_sitter_javascript as javascript
JAVASCRIPT = Language(javascript.language())
parser = Parser(JAVASCRIPT)


@dataclass
class Method():
    name:str
    params:type
    retour:type

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
class Dependance():
    path:Path
    name:str

@dataclass
class Class():
    class_type:str #Permet de déterminer si c'est une fonction, une class ou une const methode 
    path:Path
    name:str
    code: str
    method: Iterable["Method"] = field(default_factory=list)
    instance: Iterable["Instance"] = field(default_factory=list)
    children: Iterable["Dependance"] = field(default_factory=list) # type: ignore

    @classmethod
    def register(cls, node:Any,link:Path, code:str)->'Class': # type: ignore
        name = ''
        for child in node.children:
            if child.type in ("type_identifier", "identifier", "name"):
                name = code[child.start_byte:child.end_byte]
                break
        return Class(
            class_type=node.type,
            path=link,
            name=name,
            code=code,
        )

    def addMethod(self, method:Method)->'Class':
        return replace(self,method=self.method + [method])
    
    def addInstance(self, instance:Instance)->'Class':
        return replace(self,instance=self.instance + [instance])
    
    def addchildren(self, children:Dependance)->'Class':
        return replace(self,children=self.children + [children])
    

@dataclass
class Project():
    name: str
    classs : Iterable[Class]
    path:Path

class FileScanner():
    @classmethod
    def isRootParent(cls, node:Any)->bool:
        if node.parent and node.parent.type == "program":
            return True
        return False
    
    @classmethod
    def checkLexicalDeclaration(cls, node:Any,link:Path,code:str)->Class|None:
        for declarator in node.children:
            if declarator.type == "variable_declarator":
                value = declarator.child_by_field_name("value")
                if value and value.type in ("arrow_function", "function"):
                    return Class.register(node=value, link=link,code=code)
        return
    @classmethod
    def searchClass(cls, root: Any,link:Path,code:str) -> Iterable["Class"]:
        top_level_nodes = []
        for child in root.children:
            if not cls.isRootParent(child):
                continue

            if child.type == "function_declaration" or child.type == "class_declaration":
                top_level_nodes.append(Class.register(node=child, link=link,code=code))

            elif child.type == "lexical_declaration":
                result = cls.checkLexicalDeclaration(node=child,link=link,code=code)
                if isinstance(result, Class):
                    top_level_nodes.append(result)

            elif child.type == "export_statement":
                for sub in child.children:
                    if sub.type in ("function_declaration", "class_declaration"):
                        top_level_nodes.append(Class.register(node=sub, link=link,code=code))
                    elif sub.type == "lexical_declaration":
                        result = cls.checkLexicalDeclaration(node=sub,link=link,code=code)
                        if isinstance(result, Class):
                            top_level_nodes.append(result)
                    elif sub.type == "identifier":
                        continue  

        return top_level_nodes
    @classmethod
    def searchMethod(cls)->Iterable[Method]:
        pass
    @classmethod
    def searchInstance(cls)->Iterable[Instance]:#"lexical_declaration"
        pass
    @classmethod
    def searchDependancies(cls)->Iterable[Dependance]: #"export_statement"
        pass
    @classmethod
    def fileScanner(cls, link:Path, project:Project)->Project:
        contenu = link.read_text(encoding="utf-8")
        tree = parser.parse(contenu.encode(encoding="utf8"))
        root = tree.root_node
        classs = cls.searchClass(root=root,link=link, code=contenu)
        print(str(link)+': \n')
        for classe in classs:
            print(f'{classe.class_type} : {classe.name}')


class NavigateTroughtProject():
    def registerFile(self, link:Path, fileName:str, project:Project)->Project|None:
        if 'test' in fileName:
            return
        if fileName.endswith((".ts", ".tsx", ".js")):
            project = FileScanner.fileScanner(link=link,project=project)
        elif fileName.endswith((".js")):
            project = FileScanner.fileScanner(link=link,project=project)
        else:
            return
        return project
    
    def navigationProject(self,link:Path, project:Project)->Project:
        project = project 
        for root, dirs, files in os.walk(link):
            for file in files:
                if 'node_modules' in root or root == str(link):
                    continue
                chemin_complet = Path(os.path.join(root, file))
                project = self.registerFile(link=chemin_complet, fileName=file, project=project)
        return
            
    def setProject(self,link:Path)->Project:
        projectNames = str(link).split('/')
        project = Project(name=projectNames[-1],classs=[],path=link)
        result = self.navigationProject(link=link,project=project)
        return result

def main() -> None:
    try:
        command = sys.argv[1]
        link = sys.argv[2]
    except IndexError:
        print("Usage: main.py <COMMAND>")
        exit(1)
    
    if(command != "get_uml"):
        print("Unsupported command")
        sys.exit(1)
    
    folder = Path(link).resolve()
    if not folder.exists():
        print("folder not found")
        sys.exit(1)
    if not os.path.isdir(folder):
        print("path is not a folder")
        sys.exit(1)  

    navigator = NavigateTroughtProject()
    project = navigator.setProject(link=folder)
    print('analyse terminée')
    sys.exit(1)

    
if __name__ == "__main__":
    main()