from entities import Class,Method,Project
from typing import Iterable, Any, List, Callable, Optional
import re
from pathlib import Path
from tree_sitter import Node
from tree_sitter import Parser

class FileScanner():
    @classmethod
    def findDependencies(cls,classe:Class, classes: List["Class"]) ->Class:
        dependencies = []
        code_str = classe.code.decode("utf-8")
        for other in classes:
            if classe.name == other.name:
                continue
            if re.search(rf'\b{other.name}\b', code_str):
                dependencies.append(other.name)
            for alias, real_class in other.instanciation_class.items():
                if re.search(rf'\b{alias}\b', code_str):
                    dependencies.append(real_class)
        return classe.addDependencies(dependencies)
    
    @classmethod
    def extractInstanceClasseMap(cls,classe:Class, code: bytes) -> Class:
        instance_map = {}
        code_str = code.decode("utf-8")
        instantiations = re.findall(r'const\s+(\w+)\s*=\s*new\s+(\w+)\s*\(', code_str)
        temp_map = {var: class_name for var, class_name in instantiations}
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
                result = LexicalDeclaration.class_lexical_declaration(node=child,link=link,code=code)
                if isinstance(result, Class):
                    top_level_nodes.append(result)

            elif child.type == "export_statement":
                for sub in child.children:
                    if sub.type in ("function_declaration", "class_declaration","abstract_class_declaration"):
                        top_level_nodes.append(Class.register(node=sub, link=link,code=code))
                    elif sub.type == "lexical_declaration":
                        result = LexicalDeclaration.class_lexical_declaration(node=sub,link=link,code=code)
                        if isinstance(result, Class):
                            top_level_nodes.append(result)
                    elif sub.type == "identifier":
                        continue  

        return top_level_nodes
    @classmethod 
    def paramsAndReturnFinder(cls, node:Node, method:Method, classe:Class)->Class:
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
                method = method.addParam(params)
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
                        classe = classe.addMethod(method=newMethode)
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
                                        temp_classe = classe.registerNode(node=body)
                                        newclasse = cls.searchMethod(temp_classe)
                                        for method in newclasse.method:
                                            classe = classe.addMethod(method=method) 
                                    break
            if child.type == "lexical_declaration":
                # Appeler la méthode d'extraction de la méthode 
                classe.addMethod(method=LexicalDeclaration.method_lexical_declaration(node=child))
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

class Params():
    @classmethod
    def extract_args(cls, node:Node, code:str)->List[str]:
        params = []
        for declarator in node.children:
            if declarator.type == 'required_parameters':
                return cls.extract_formal_paramters(node=declarator)
            if declarator.type != 'object_pattern':
                continue
            for parameters in declarator.children:
                if parameters.type != 'shorthand_property_identifier_pattern':
                    continue
                params.append(code[parameters.start_byte:parameters.end_byte].decode("utf-8"))
        return params
    @classmethod
    def extract_formal_paramters(cls, node:Node, code:str)->List[str]:
        params = []
        for declarator in node.children:
            if declarator.type == 'required_parameters':
                pattern = declarator.child_by_field_name("pattern")
                if pattern.type == 'object_pattern':
                    for parameters in declarator.children:
                        if parameters.type != 'shorthand_property_identifier_pattern':
                            continue
                        params.append(code[parameters.start_byte:parameters.end_byte].decode("utf-8"))
                if pattern.type == 'identifier':
                    params.append(code[pattern.start_byte:pattern.end_byte].decode("utf-8"))
        return params
    
class LexicalDeclaration():
    @classmethod
    def class_lexical_declaration(cls, node:Any,link:Path,code:str)->Class|None:
        for declarator in node.children:
            if declarator.type == "variable_declarator":
                name_node = declarator.child_by_field_name("name")
                value = declarator.child_by_field_name("value")
                if name_node and value and value.type in ("arrow_function", "function"):
                    func_name = code[name_node.start_byte:name_node.end_byte].decode("utf-8")
                    params_node = value.child_by_field_name("parameters")
                    body_node = value.child_by_field_name("body")

                    params_str = code[params_node.start_byte:params_node.end_byte].decode("utf-8")
                    params = FileScanner.extract_param_list(params_node,code)
                    
                    return_fields = list(set(FileScanner.extract_return_keys(body_node, code, params_str))) if body_node else []

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
    def method_lexical_declaration(cls, node:Node)->Method:
        for declarator in node.children:
            if declarator.type != "variable_declarator":
                continue
            name = declarator.child_by_field_name("name")
            type = declarator.child_by_field_name("value")
            if name and type : 
                if not type.type in ("arrow_function", "function"): 
                    continue
                params = type.child_by_field_name("parameters")  # Créer une méthode qui extrait proprement ca au lieu de sortir (text: string)
                retour = type.child_by_field_name("return_type") #Créer une méthode qui extrait proprement les retours au lieu de sortir : string
                if retour: 
                    method = Method(name=name, params=params, retour=retour)
                else : 
                    func_name = classe.code[name.start_byte:name.end_byte].decode("utf-8")
                    method = Method(name=func_name)
                    newMethode = cls.paramsAndReturnFinder(node=type, method=method, classe=classe)
                    classe = classe.addMethod(method=newMethode)
    @classmethod
    def parse_lexical_declaration(cls, node: Node) -> Optional[Any]:
        for declarator in node.children:
            if declarator.type != "variable_declarator":
                continue

            name_node = declarator.child_by_field_name("name")
            value_node = declarator.child_by_field_name("value")

            if not name_node or not value_node:
                continue
            return {'name_node':name_node,'value_node':value_node}

