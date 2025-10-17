import json
from graphviz import Digraph

path = input("Enter JSON path: ").strip()
with open(path, "r") as file:
    data = json.load(file)

Relation = Digraph(comment="Relational Diagram", format="png")
Relation.attr(splines="spline", bgcolor="white")  
foreign_keys = []
tables ={}

for entity in data["entities"]:
    if entity.get("isWeak",False) == False:
        table_name = entity["name"].strip()
        primary_keys = []
        attr = []

#==========================HANDLE PRIMARY KEYS========================      
        for attribute in entity["attributes"]:  #get all primary keys first to be used in multivalued attr
            attribute_name = attribute["name"]
            is_pk = attribute.get("isPrimaryKey", False) 
            composite = attribute.get("composite", [])  
            if is_pk and composite:                #if pk and composite
                for sub_attribute in composite:
                  primary_keys.append(sub_attribute)
            elif is_pk and not composite :
                primary_keys.append(attribute_name)

#================================HANDLE COMPOSITE AND MULTIVALUED==============================             
        for attribute in entity["attributes"]:
            attribute_name = attribute["name"]
            composite = attribute.get("composite", [])
            is_pk = attribute.get("isPrimaryKey", False) 
            ismulti = attribute.get("isMultiValued", False)

            if composite and not is_pk and not ismulti:
                for sub_attribute in composite:
                    attr.append(sub_attribute)
            elif ismulti:
                multi_table_name = f'{table_name}_{attribute_name}'
                multi_pk = []
                multi_fk = []
                
                for i in primary_keys :
                   fk_attr_name = f'{table_name}_{i}'
                   multi_pk.append(fk_attr_name)
                   multi_fk.append(fk_attr_name)
                   foreign_keys.append({
                       'from_table' :  multi_table_name ,
                       'from_attr' :  fk_attr_name ,
                       'to_table' : table_name ,
                       'to_attr' : i
                   })
                if composite:
                    multi_pk.extend(composite)
                    
                else:
                    multi_pk.append(attribute_name)   
                     

                tables[multi_table_name] = {'pk' : multi_pk,'fk' : multi_fk ,'attributes' :[]}   

            else :
               if not is_pk : 
                attr.append(attribute_name)

        tables[table_name] = {'pk': primary_keys ,'fk' : [] ,'attributes' : attr}                    
#=========================================WEAK ENTITY======================================================

    else :
        table_name = entity["name"].strip() 
        tables[table_name] = {'pk': [], 'fk' : [] , 'attributes': []}
        relation_attr = []
        for rel in data.get("relationships", []):
                if rel.get("isIdentifying"):
                    entities_in_rel = [e['name'] for e in rel['entities']]
                    if table_name in entities_in_rel:
                        identiying_name = next((name for name in entities_in_rel if name != table_name), None)
                        for attribute in rel.get("attributes", []):  
                            attribute_name = attribute["name"]
                            relation_attr.append(attribute_name)
                        break

        identifying_pks = tables[identiying_name]['pk'] 
        fk_columns = [f"{identiying_name}_{pk}" for pk in identifying_pks]
        partial_keys = []
        normal_attr = []
        for attr in entity["attributes"]:
                if attr.get("isPartialKey"):
                    partial_keys.append(attr["name"])
                elif "composite" in attr:
                    normal_attr.extend(attr["composite"])
                else:
                    normal_attr.append(attr["name"])
        
        tables[table_name]['pk'] = fk_columns + partial_keys
        tables[table_name]['fk'] = fk_columns
        tables[table_name]['attributes'] = normal_attr
        for i in relation_attr :
          tables[table_name]['attributes'].append(i)

        for i, pk in enumerate(identifying_pks):
                foreign_keys.append({
                    'from_table': table_name, 'from_attr': fk_columns[i],
                    'to_table': identiying_name, 'to_attr': pk
                })

#=======================================HANDLE RELATIONSHIPS===========================================
for rel in data.get("relationships", []):
        if rel.get("isIdentifying"): continue   #already handeled it

        e1, e2 = rel['entities'][0]["name"], rel['entities'][1]["name"]
        cardinality = f"{rel['entities'][0]["cardinality"]}:{rel['entities'][1]["cardinality"]}"

        if cardinality == "N:1":
            many_table, one_table = e1, e2
        elif cardinality == "1:N":
            many_table, one_table = e2, e1
        else :                                  #IN CASE 1:1 I USED  Cross-reference RELATION BECAUSE NO INFO ABOUT PARTICIPATION
            new_relation_tableName =  rel['name'] 
            rel_pk = [] 
            rel_fk=[]
            first_table_pks = tables[e1]['pk']
            second_table_pks = tables[e2]['pk']
            for pk in first_table_pks :
                fk_col_name = f"{e1}_{pk}"
                rel_fk.append(fk_col_name)
                rel_pk.append(fk_col_name) 
                foreign_keys.append({
                    'from_table': new_relation_tableName,
                    'from_attr': fk_col_name,
                    'to_table': e1,
                    'to_attr': pk
                })

            for pk in second_table_pks :
                fk_col_name = f"{e2}_{pk}"
                rel_pk.append(fk_col_name) 
                rel_fk.append(fk_col_name)
                foreign_keys.append({
                    'from_table': new_relation_tableName,
                    'from_attr': fk_col_name,
                    'to_table': e2,
                    'to_attr': pk
                })  
            rel_attr = []
            for attribute in rel.get("attributes", []): 
                attribute_name = attribute["name"]
                rel_attr.append(attribute_name)
            tables[new_relation_tableName] = {'pk': rel_pk ,'fk' : rel_fk, 'attributes' : rel_attr}    
                
    
        if cardinality == "N:1" or cardinality == "1:N" : 
            one_table_pks = tables[one_table]['pk']
            many_table_fks =[]
            for pk in one_table_pks:
                fk_col_name = f"{one_table}_{pk}"
                if fk_col_name not in tables[many_table]['attributes']:
                    tables[many_table]['fk'].append(fk_col_name)
                    foreign_keys.append({
                        'from_table': many_table,
                        'from_attr': fk_col_name,
                        'to_table': one_table,
                        'to_attr': pk
                    })  
            for attribute in rel.get("attributes", []):  
                attribute_name = attribute["name"]
                tables[many_table]['attributes'].append(attribute_name)
                         


##################################CONNECT FOREIGN KEYS################################3        

for table_name, table_data in tables.items():
    label = f'<<table BORDER="0" CELLBORDER="1" CELLSPACING="0" CELLPADDING="4"><tr><td COLSPAN="2" BGCOLOR="lightblue"><b>{table_name}</b></td></tr>\n'
    for pk in table_data['pk'] :
       if pk in table_data['fk'] : 
            name = f'<u>{pk}</u>'
            key_marker = "PK , FK"
            label += f'<TR><TD port="{pk}">{name}</TD><TD>{key_marker}</TD></TR>\n'
       else:
            name = f'<u>{pk}</u>'
            key_marker = "PK"
            label += f'<TR><TD port="{pk}">{name}</TD><TD>{key_marker}</TD></TR>\n'
    for fk in table_data['fk'] :
        if fk not in  table_data['pk'] :
            name = f'{fk}'
            key_marker = "FK"
            label += f'<TR><TD port="{fk}">{name}</TD><TD>{key_marker}</TD></TR>\n'

              
    for attr in table_data['attributes'] :
        label += f'<TR><TD port = "{attr}">{attr}</TD><TD></TD></TR>\n'      

    label += '</table>>'   
    Relation.node(table_name , label = label , shape = 'plain')
         
for fk in foreign_keys:
        Relation.edge(
            f"{fk['from_table']}:{fk['from_attr']}",
            f"{fk['to_table']}:{fk['to_attr']}"
        )
        

Relation.render(filename="ER-to-Relation/Relational diagram", view=True, cleanup=False)

    


