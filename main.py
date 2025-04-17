import os
import sys
from pathlib import Path
from uml_generator.entities import Project
from uml_generator.file_scanner import FileScanner

from tree_sitter import Language, Parser
import tree_sitter_javascript as javascript
import tree_sitter_typescript as typescript

JAVASCRIPT = Language(javascript.language())
TSX = Language(typescript.language_tsx())
TS = Language(typescript.language_typescript())


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