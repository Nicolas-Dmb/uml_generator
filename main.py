from dataclasses import dataclass, field, replace
import os
import re
import sys
from pathlib import Path
from typing import Dict, Iterable, Any, List, Optional
from tree_sitter import Language, Node, Parser
import tree_sitter_javascript as javascript
import tree_sitter_typescript as typescript
JAVASCRIPT = Language(javascript.language())
TSX = Language(typescript.language_tsx())
TS = Language(typescript.language_typescript())



@dataclass
class Method():
    name:str
    params:list[str] = field(default_factory=list)
    retour:list[str] = field(default_factory=list)

    def addReturn(self,returnType)->'Method':
        if returnType in self.retour:
            return self
        return replace(self, retour=self.retour + [returnType])

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
    class_type:str #Permet de déterminer si c'est une fonction, une class ou une const methode 
    path:Path
    name:str
    code: str
    node: Node
    method: Iterable["Method"] = field(default_factory=list)
    instance: Iterable["Instance"] = field(default_factory=list)
    children: Iterable["str"] = field(default_factory=list)
    params: Iterable["str"] = field(default_factory=list)
    retour: Iterable["str"] = field(default_factory=list)
    instanciation_class: Dict[str,str] = field(default_factory=dict)

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

    def addMethod(self, name:Node, params: Node | None, retour: Node | None)->'Class':
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
    

@dataclass
class Project():
    name: str
    classs : Iterable[Class]
    path:Path

    def addClasses(self,classes:Iterable[Class])->'Project':
        return replace(self,classs=self.classs+classes)

class FileScanner():
    @classmethod
    def findDependencies(cls,classe:Class, classes: List["Class"]) ->Class:
        dependencies = []

        code_str = classe.code.decode("utf-8")

        for other in classes:
            if classe.name == other.name:
                continue  # pas de dépendance à soi-même

            # 🔍 Recherche directe par nom de classe
            if re.search(rf'\b{other.name}\b', code_str):
                dependencies.append(other.name)

            # 🔍 Recherche via instance aliases
            for alias, real_class in other.instanciation_class.items():
                if re.search(rf'\b{alias}\b', code_str):
                    dependencies.append(real_class)

        return classe.addDependencies(dependencies)
    @classmethod
    def extractInstanceClasseMap(cls,classe:Class, code: bytes) -> Class:
        instance_map = {}
        code_str = code.decode("utf-8")

        # Étape 1 : extraire toutes les instances de `const x = new ClassName(...)`
        instantiations = re.findall(r'const\s+(\w+)\s*=\s*new\s+(\w+)\s*\(', code_str)

        temp_map = {var: class_name for var, class_name in instantiations}

        # Étape 2 : chercher un return { ... } avec des propriétés raccourcies
        return_blocks = re.findall(r'return\s*{\s*([\w\s,]+)\s*}', code_str)

        for block in return_blocks:
            props = [p.strip() for p in block.split(',') if p.strip()]
            for prop in props:
                if prop in temp_map:
                    instance_map[prop] = temp_map[prop]

        return classe.addInstanciation_class(instance_map)
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
                value = declarator.child_by_field_name("value")
                if name_node and value and value.type in ("arrow_function", "function"):
                    func_name = code[name_node.start_byte:name_node.end_byte].decode("utf-8")
                    params_node = value.child_by_field_name("parameters")
                    body_node = value.child_by_field_name("body")

                    params_str = code[params_node.start_byte:params_node.end_byte].decode("utf-8")
                    params = cls.extract_param_list(params_node,code)
                    
                    return_fields = list(set(cls.extract_return_keys(body_node, code, params_str))) if body_node else []
                    if func_name == 'CheckListView':
                        print("🚨🚨 passage ici ")
                    return Class(
                        class_type=value.type,
                        path=link,
                        name=func_name,
                        code=code,
                        node=value, 
                        params=params,
                        retour=return_fields,

                    )
                elif name_node: 
                    return cls.checkStyleSheet(node=declarator,link=link,code=code)
        return
    @classmethod
    def extract_param_list(cls, params_node: Node, code: bytes) -> list[str]:
        params = []
        if not params_node:
            return params

        for child in params_node.children:
            if child.type == "required_parameter":
                pattern = child.child_by_field_name("pattern")
                if not pattern:
                    continue

                # Si c'est un identifiant simple
                if pattern.type == "identifier":
                    param_name = code[pattern.start_byte:pattern.end_byte].decode("utf-8")
                    params.append(param_name)

                # Si c'est un objet destructuré : { x, y }
                elif pattern.type == "object_pattern":
                    for prop in pattern.named_children:
                        if prop.type == "identifier":
                            name = code[prop.start_byte:prop.end_byte].decode("utf-8")
                            params.append(name)

                # Tu peux aussi gérer array_pattern ici plus tard
            elif child.type == "identifier":
                # Arrow function en mode x => {...}
                name = code[child.start_byte:child.end_byte].decode("utf-8")
                params.append(name)

        return params
    @classmethod
    def extract_return_keys(cls,body_node: Node, code: bytes, params:str) -> list[str]:
        keys = []
        cursor = body_node.walk()
        reached_root = False

        while not reached_root:
            node = cursor.node

            if node.type == "return_statement":
                expr = node.child_by_field_name("argument")
                if expr and expr.type == "object":
                    for prop in expr.named_children:
                        if prop.type == "pair":
                            key_node = prop.child_by_field_name("key")
                            if key_node:
                                key = code[key_node.start_byte:key_node.end_byte].decode("utf-8")
                                keys.append(key)
                        elif prop.type == "identifier" or prop.type == "shorthand_property_identifier":
                            key = code[prop.start_byte:prop.end_byte].decode("utf-8")
                            keys.append(key)
            if node.type == "call_expression":
                func_node = node.child_by_field_name("function")
                retour = code[func_node.start_byte:func_node.end_byte].decode("utf-8")
                if retour in params:

                    keys.append(retour)
            if cursor.goto_first_child():
                continue
            if cursor.goto_next_sibling():
                continue

            while True:
                if not cursor.goto_parent():
                    reached_root = True
                    break
                if cursor.goto_next_sibling():
                    break

        return keys
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
    def paramsAndReturnFinder(cls, node:Node, method:Method, classe:Class)->Method:
        method=method
        for child in node.children:
            if child.type == "lexical_declaration":
                continue
            if child.type == "call_expression":
                func_node = child.child_by_field_name("function")
                retour = classe.code[func_node.start_byte:func_node.end_byte].decode("utf-8")
                if retour != "console.log":
                    method = method.addReturn(returnType=retour)
            if child.type == "required_parameter":
                params = classe.code[child.start_byte:child.end_byte].decode("utf-8")if child else ""
                method = replace(method, params=method.params+[params])  # Je pense que ca ne passe jamais ici 
            else : 
                method = cls.paramsAndReturnFinder(node=child, method=method, classe=classe)
        return method
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
                classe = classe.addMethod(name=name,params=args,retour=return_type)
            if child.type == "method_definition":
                name = child.child_by_field_name("name")
                args = child.child_by_field_name("parameters")
                return_type = child.child_by_field_name("return_type")
                if return_type:
                    args = child.child_by_field_name("parameters")
                    return_type = child.child_by_field_name("return_type")
                    if name and args and return_type : 
                        classe = classe.addMethod(name=name,params=args,retour=return_type)
                else:
                    nameString = classe.code[name.start_byte:name.end_byte].decode("utf-8")
                    if nameString != 'constructor':
                        method = Method(name=nameString)
                        newMethode = cls.paramsAndReturnFinder(node=child, method=method, classe=classe)
                        classe = replace(classe, method=classe.method + [newMethode]) # Je pense que ca c'est jamais utilisée car replace n'est pas possible ailleurs que dans la class 
            if child.type == "expression_statement":
                call_expr = child.child_by_field_name("expression")
                if call_expr and call_expr.type == "call_expression":
                    func = call_expr.child_by_field_name("function")
                    args = child.child_by_field_name("arguments")
                    if func:
                        if not any(c.type == "array" for c in args.children):
                            classe = classe.addMethod(name=func, params=args, retour=None)
                        else : 
                            for arg_node in args.named_children:
                                if arg_node.type == "arrow_function":
                                    classe = classe.addMethod(name=func, params=None, retour=None)
                                    body = arg_node.child_by_field_name("body")
                                    if body:
                                        temp_classe = replace(classe, node=body)
                                        newclasse = cls.searchMethod(temp_classe)
                                        classe = replace(classe,method=classe.method + newclasse.method)
                                    break
            if child.type == "lexical_declaration":
                for declarator in child.children:
                    if declarator.type == "variable_declarator":
                        name = declarator.child_by_field_name("name")
                        type = declarator.child_by_field_name("value")
                        if name and type : 
                            if type.type in ("arrow_function", "function"): 
                                params = type.child_by_field_name("parameters")  # Créer une méthode qui extrait proprement ca au lieu de sortir (text: string)
                                retour = type.child_by_field_name("return_type") #Créer une méthode qui extrait proprement les retours au lieu de sortir : string
                                if retour: 
                                    classe = classe.addMethod(name=name, params=params, retour=retour)
                                else : 
                                    func_name = classe.code[name.start_byte:name.end_byte].decode("utf-8")
                                    method = Method(name=func_name)
                                    newMethode = cls.paramsAndReturnFinder(node=type, method=method, classe=classe)
                                    classe = replace(classe, method=classe.method + [newMethode])
        return classe
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
        return classe
        
    @classmethod
    def fileScanner(cls, link:Path, project:Project, parser:Parser)->Project:
        contenu = link.read_text(encoding="utf-8")
        code_bytes = contenu.encode("utf-8")
        tree = parser.parse(code_bytes)
        root = tree.root_node
        classs = cls.searchClass(root=root,link=link, code=code_bytes)
        new_classs = []
        for classe in classs:
            classeWithInstance = cls.searchInstance(classe)
            classeWithMethod = cls.searchMethod(classeWithInstance)
            classeWithInstance = cls.extractInstanceClasseMap(classeWithMethod,classe.code)
            new_classs.append(classeWithInstance)
        final_list_classes = []
        for classe in new_classs:
            classWihtDependancies = cls.findDependencies(classe=classe,classes=new_classs)
            final_list_classes.append(classWihtDependancies)
        return project.addClasses(final_list_classes)


class NavigateTroughtProject():
    def registerFile(self, link:Path, fileName:str, project:Project)->Project|None:
        if 'test' in fileName:
            return project 
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
            return project
        return project
    
    def navigationProject(self,link:Path, project:Project)->Project:
        project = project 
        for root, dirs, files in os.walk(link):
            for file in files:
                if 'node_modules' in root or root == str(link):
                    continue
                chemin_complet = Path(os.path.join(root, file))
                project = self.registerFile(link=chemin_complet, fileName=file, project=project)
        return project
            
    def setProject(self,link:Path)->Project:
        projectNames = str(link).split('/')
        project = Project(name=projectNames[-1],classs=[],path=link)
        result = self.navigationProject(link=link,project=project)
        return result
    
def generate_mermaid(project: Project) -> str:
    lines = [f"classDiagram", f'%% Diagramme UML du projet "{project.name}"']
    print(f"💡 Nombre de classes dans le projet : {len(project.classs)}")
    for classe in project.classs:
        # Déclaration de la classe/fonction
        # print(f"🧱 {classe.name} ({classe.class_type}) → méthodes : {len(c.method)} / dépendances : {c.children}")
        label = f"class {classe.name}"
        stereotype = f"«{classe.class_type}»"
        lines.append(f"{label} {{")
        lines.append(f"  {stereotype}")
        
        # Ajout des paramètres
        for param in classe.params:
            lines.append(f"  +{param}")
        
        # Ajout des méthodes
        for method in classe.method:
            params = ", ".join(method.params) if isinstance(method.params, list) else ""
            retour = f": {method.retour}" if method.retour else ""
            lines.append(f"  +{method.name}({params}){retour}")
        
        lines.append("}")

    # Lien de dépendances
    for classe in project.classs:
        for dependency in classe.children:
            lines.append(f"{classe.name} --> {dependency}")

    return "\n".join(lines)

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
    uml_code = generate_mermaid(project)

    with open("diagram.mmd", "w") as f:
        f.write(uml_code)
    print('analyse terminée')
    sys.exit(1)

    
if __name__ == "__main__":
    main()