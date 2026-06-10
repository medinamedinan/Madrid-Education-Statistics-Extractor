import pandas as pd
from playwright.sync_api import sync_playwright
from bs4 import BeautifulSoup
from io import StringIO
import re

print("1. Leyendo y filtrando institutos de la Zona Sur...")
df = pd.read_csv("centros_educativos.csv", sep=';', encoding='utf-8')

es_publico = df['TITULARIDAD'].astype(str).str.strip().str.upper() == 'PÚBLICO'
es_ies_o_cepa = df['TIPO_ABRV'].astype(str).str.contains('IES|CEPA', case=False, na=False)
ciudades = 'GETAFE|LEGANÉS|LEGANES|PINTO|PARLA'
es_zona_sur = df['MUNICIPIO'].astype(str).str.contains(ciudades, case=False, na=False)

df_filtrado = df[es_publico & es_ies_o_cepa & es_zona_sur]
codigos_a_buscar = df_filtrado['CODIGO'].tolist()

print(f"✅ Se van a analizar {len(codigos_a_buscar)} institutos.")

resultados = []
total = len(codigos_a_buscar)
contador = 1


# --- FUNCIONES MATEMÁTICAS (Para arreglar los 685 -> 6.85) ---
def limpiar_nota(valor):
    try:
        v = str(valor).replace(',', '.').strip()
        if v.lower() == 'nan' or not v: return "Sin datos"
        f = float(v)
        while f > 14: f = f / 10  # La EvAU máxima es 14
        return f"{f:.2f}"
    except:
        return str(valor)


def limpiar_porcentaje(valor):
    try:
        v = str(valor).replace(',', '.').replace('%', '').strip()
        if v.lower() == 'nan' or not v: return "Sin datos"
        f = float(v)
        while f > 100: f = f / 10  # Si pone 854, lo pasa a 85.4%
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


# -----------------------------------------------------------

# --- LA NUEVA HERRAMIENTA: EL "CLICADOR" INTELIGENTE ---
def hacer_clic_y_leer(page, texto_boton, palabra_tabla, funcion_limpieza):
    try:
        # Busca todos los botoncitos redondos que contengan ese texto y les hace clic
        botones = page.locator(f"text='{texto_boton}'").all()
        for btn in botones:
            try:
                btn.click(force=True, timeout=1000)
            except:
                pass

        # Esperamos a que la web cargue la tabla nueva tras el clic
        page.wait_for_timeout(800)

        # Leemos el código HTML nuevo
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


# -------------------------------------------------------

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    page = browser.new_page()

    for codigo in codigos_a_buscar:
        url = f"https://gestiona.comunidad.madrid/wpad_pub/run/j/MostrarFichaCentro.icm?cdCentro={codigo}"

        try:
            page.goto(url, timeout=20000)
            page.wait_for_timeout(1000)

            # Anti-Null
            if page.locator("body").inner_text().strip().lower() == "null":
                page.wait_for_timeout(2000)

            texto_cuerpo = page.locator("body").inner_text().lower()
            tiene_tarde = "tarde" in texto_cuerpo or "vespertino" in texto_cuerpo
            es_semipresencial = "semipresencial" in texto_cuerpo or "distancia" in texto_cuerpo

            if tiene_tarde or es_semipresencial:
                nombre = df_filtrado[df_filtrado['CODIGO'] == codigo]['CENTRO'].values[0]
                municipio = df_filtrado[df_filtrado['CODIGO'] == codigo]['MUNICIPIO'].values[0]
                zona = df_filtrado[df_filtrado['CODIGO'] == codigo]['DAT'].values[0]

                datos = {
                    "Matric_Bach": "Sin datos", "Matric_EvAU": "Sin datos",
                    "Present_EvAU": "Sin datos", "Nota_Expediente": "Sin datos",
                    "Nota_EvAU": "Sin datos", "%_Titulacion_ESO": "Sin datos"
                }

                # 1. ENTRAR A LA PESTAÑA PRINCIPAL
                try:
                    page.get_by_text("RESULTADOS ACADÉMICOS", exact=False).first.click(force=True)
                    page.wait_for_timeout(1500)
                except:
                    pass

                # 2. SECCIÓN EvAU: Hacer clics en los botones
                datos["Nota_EvAU"] = hacer_clic_y_leer(page, "Nota media Bloque", "PAU", limpiar_nota)
                datos["Nota_Expediente"] = hacer_clic_y_leer(page, "Nota media del expediente", "PAU", limpiar_nota)
                datos["Present_EvAU"] = hacer_clic_y_leer(page, "alumnos presentados", "PAU", limpiar_entero)
                # (Nota: La web no suele mostrar matriculados para la EvAU, pero por si acaso, probamos)
                datos["Matric_EvAU"] = hacer_clic_y_leer(page, "matriculados", "PAU", limpiar_entero)

                # 3. SECCIÓN ESO: Clic en el botón "ESO" y luego en el botón "% que titula"
                try:
                    page.locator("label:has-text('ESO')").first.click(force=True, timeout=1000)
                except:
                    pass
                datos["%_Titulacion_ESO"] = hacer_clic_y_leer(page, "que titula", "SECUNDARIA", limpiar_porcentaje)

                # 4. SECCIÓN BACHILLERATO: Clic en "Bachillerato" y luego en "Alumnos matriculados"
                try:
                    page.locator("label:has-text('Bachillerato')").first.click(force=True, timeout=1000)
                except:
                    pass
                datos["Matric_Bach"] = hacer_clic_y_leer(page, "matriculados", "BACHILLERATO", limpiar_entero)

                # GUARDAR
                resultados.append({
                    "Codigo": codigo, "Nombre": nombre, "Zona": zona, "Municipio": municipio,
                    "Turno_Tarde": "Sí" if tiene_tarde else "No",
                    "Semipresencial": "Sí" if es_semipresencial else "No",
                    "%_Titulacion_ESO": datos["%_Titulacion_ESO"],
                    "Nota_Media_EvAU": datos["Nota_EvAU"],
                    "Nota_Media_Expediente": datos["Nota_Expediente"],
                    "Presentados_EvAU": datos["Present_EvAU"],
                    "Matriculados_EvAU": datos["Matric_EvAU"],
                    "Matriculados_Bachillerato": datos["Matric_Bach"],
                    "URL": url
                })

                print(f"[{contador}/{total}] 🎯 {nombre}")
                print(
                    f"      ESO: {datos['%_Titulacion_ESO']} | EvAU: {datos['Nota_EvAU']} | Exp: {datos['Nota_Expediente']}")
                print(
                    f"      Bach_Matr: {datos['Matric_Bach']} | EvAU_Matr: {datos['Matric_EvAU']} | EvAU_Pres: {datos['Present_EvAU']}")

            else:
                print(f"[{contador}/{total}] Descartado (No tiene horario de tarde)")

        except Exception as e:
            print(f"[{contador}/{total}] ❌ Error conectando a la web")

        contador += 1

    browser.close()

print("\n3. Guardando Excel final...")
if len(resultados) > 0:
    df_resultados = pd.DataFrame(resultados)
    df_resultados.to_csv("Institutos_Sur_Extraccion_Clics.csv", index=False, encoding='utf-8-sig', sep=';')
    print("¡Éxito! Archivo generado con el método de simulación humana real.")
