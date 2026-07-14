from flask import Flask, render_template

def Invetario_ruta():
    
    return render_template("inventario.html", title="Inventario", template="inventario-template")