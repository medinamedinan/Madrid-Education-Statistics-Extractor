import pandas as pd
from bs4 import BeautifulSoup
from io import StringIO

def limpiar_nota(valor):
    try:
        v = str(valor).replace(',', '.').strip()
        if v.lower() == 'nan' or not v: return "Sin datos"
        f = float(v)
        while f > 14: f = f / 10  
        return f"{f:.2f}"
    except:
        return str(valor)

def limpiar_porcentaje(valor):
    try:
        v = str(valor).replace(',', '.').replace('%', '').strip()
        if v.lower() == 'nan' or not v: return "Sin datos"
        f = float(v)
        while f > 100: f = f / 10  
        return f"{f:.2f}%"
    except:
        return str(valor)

def limpiar_entero(valor):
    try:
        v = str(valor).replace(',', '').replace('.', '').strip()
        if v.lower() == 'nan' or not v: return "Sin datos"
        return str(int(float(v)))
    except:
        return str(valor)

def hacer_clic_y_leer(page, texto_boton, palabra_tabla, funcion_limpieza):
    try:
        botones = page.locator(f"text='{texto_boton}'").all()
        for btn in botones:
            try:
                btn.click(force=True, timeout=1000)
            except:
                pass

        page.wait_for_timeout(800)
        html = page.content()
        soup = BeautifulSoup(html, 'html.parser')

        for tabla in soup.find_all('table'):
            if palabra_tabla.lower() in tabla.get_text().lower():
                try:
                    df_t = pd.read_html(StringIO(str(tabla)), decimal=',', thousands='.')[0]
                    fila_centro = df_t[df_t.iloc[:, 0].astype(str).str.contains('centro', case=False, na=False)]
                    if not fila_centro.empty:
                        valor = str(fila_centro.iloc[0, -1]).strip()
                        if valor.lower() != 'nan' and valor != '':
                            return funcion_limpieza(valor)
                except:
                    pass
    except:
        pass
    return "Sin datos"
