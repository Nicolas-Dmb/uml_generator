from dataclasses import dataclass, field, replace
import os
import sys
from pathlib import Path
from typing import Iterable, Any
from tree_sitter import Language, Node, Parser
import tree_sitter_javascript as javascript
import tree_sitter_typescript as typescript
JAVASCRIPT = Language(javascript.language())
TSX = Language(typescript.language_tsx())
TS = Language(typescript.language_typescript())



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
    node: Node
    method: Iterable["Method"] = field(default_factory=list)
    instance: Iterable["Instance"] = field(default_factory=list)
    children: Iterable["Dependance"] = field(default_factory=list) # type: ignore

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

    def addMethod(self, method:Method)->'Class':
        return replace(self,method=self.method + [method])
    
    def addInstance(self,name:Node, type:Node)->'Class':
        nameString = self.code[name.start_byte:name.end_byte].decode("utf-8")
        typeString = self.code[type.start_byte:type.end_byte].decode("utf-8")
        instance = Instance(name=nameString, type=typeString)
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
    def checkStyleSheet(cls, node:Any,link:Path,code:str)->Class|None:
        value_node = node.child_by_field_name("value")
        if value_node and value_node.type == "call_expression":
            func_node = value_node.child_by_field_name("function")
            if func_node and func_node.type == "member_expression":
                object_node = func_node.child_by_field_name("object")
                object_text = code[object_node.start_byte:object_node.end_byte].decode("utf-8") if object_node else ""
                if object_text == "StyleSheet":
                    return
        return Class.register(node=node, link=link,code=code)
    @classmethod
    def checkLexicalDeclaration(cls, node:Any,link:Path,code:str)->Class|None:
        for declarator in node.children:
            if declarator.type == "variable_declarator":
                name_node = declarator.child_by_field_name("name")
                if name_node: 
                    return cls.checkStyleSheet(node=declarator,link=link,code=code)
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
                    if sub.type in ("function_declaration", "class_declaration","abstract_class_declaration"):
                        top_level_nodes.append(Class.register(node=sub, link=link,code=code))
                    elif sub.type == "lexical_declaration":
                        result = cls.checkLexicalDeclaration(node=sub,link=link,code=code)
                        if isinstance(result, Class):
                            top_level_nodes.append(result)
                    elif sub.type == "identifier":
                        continue  

        return top_level_nodes
    @classmethod
    def searchMethod(cls, classe:Class)->Class:
        classe = classe
        class_body = classe.node.child_by_field_name("body")
        if not class_body : 
            return classe
        for child in class_body.children:
            if child.type == "abstract_method_signature":
                name = child.child_by_field_name("name")
                args = child.child_by_field_name("parameters")
                return_type = child.child_by_field_name("return_type")
                
        pass
    @classmethod
    def searchInstance(cls, classe:Class)->Class:#"lexical_declaration"
        classe = classe
        class_body = classe.node.child_by_field_name("body")
        if not class_body : 
            return classe
        for child in class_body.children:
            if child.type == "public_field_definition":
                name = child.child_by_field_name("name")
                type = child.child_by_field_name("type")
                if name and type : 
                    classe = classe.addInstance(name=name,type=type)
            if child.type == "lexical_declaration":
                for declarator in child.children:
                    if declarator.type == "variable_declarator":
                        name = declarator.child_by_field_name("name")
                        type = declarator.child_by_field_name("value")
                        if name and type : 
                            if type.type not in ("arrow_function", "function"): 
                                classe = classe.addInstance(name=name,type=type)
            #if child.type == "abstract_method_signature":
        return classe
        
    @classmethod
    def searchDependancies(cls)->Iterable[Dependance]: #"export_statement"
        pass
    @classmethod
    def fileScanner(cls, link:Path, project:Project, parser:Parser)->Project:
        contenu = link.read_text(encoding="utf-8")
        code_bytes = contenu.encode("utf-8")
        tree = parser.parse(code_bytes)
        root = tree.root_node
        classs = cls.searchClass(root=root,link=link, code=code_bytes)
        for classe in classs:
            Newclasse = cls.searchInstance(classe)
            if Newclasse:
                print(link,'\n')
                print(f"🗞️ classe : {Newclasse.name} : {Newclasse.instance}")
            else:
                print(f"🚨 erreur sur la classe {classe.name} / {classe.path}")


class NavigateTroughtProject():
    def registerFile(self, link:Path, fileName:str, project:Project)->Project|None:
        if 'test' in fileName:
            return
        if fileName.endswith((".tsx",)):
            parser = Parser(TSX)
            project = FileScanner.fileScanner(link=link,project=project,parser=parser)
        elif fileName.endswith((".ts")):
            parser = Parser(TS)
            project = FileScanner.fileScanner(link=link,project=project,parser=parser)
        elif fileName.endswith((".js")):
            parser = Parser(JAVASCRIPT)
            project = FileScanner.fileScanner(link=link,project=project, parser=parser)
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