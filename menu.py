
def opcion_1():
    print("opcion1 ")

def opcion_2():
    print("opcion2 ")

    
def opcion_3():
    print("opcion3 ")

    
def opcion_4():
    print("opcion4 ")



def mostrar_menu_opciones():
    print("-----------MENU-----------")
    #print("Selecciona la opción: ")
    print("[1] Listar slices")
    print("[2] Crear slice ")
    print("[3] Editar slice ")
    print("[4] Borrar slice ")
    print("[5] Salir ")
    
   
#Menu del administrador del sistema
def main():
    while True:
        mostrar_menu_opciones() 
        try:
            opcion_str = input("Ingresa la opción: ")
            opcion_int = int(opcion_str)
            match opcion_int:
                case 1:
                    opcion_1()
                case 2:
                    opcion_2()
                case 3:
                    opcion_3()
                case 4:
                    opcion_4()
                case 5:
                    break
                case _:  # opcion invalida
                    print("ERROR - Ingresa una opción válida ")
            

            
        except:
            print("ERROR - Ingresa un número ")
        

if __name__ == "__main__":
    main()