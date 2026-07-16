import pandas as pd
from playwright.sync_api import sync_playwright
import re
# Importamos las funciones desde tu nuevo archivo utils.py
from utils import limpiar_nota, limpiar_porcentaje, limpiar_entero, hacer_clic_y_leer

print("1. Leyendo y filtrando institutos de la Zona Sur...")
# La ruta cambia para buscar el archivo en la carpeta 'data'
df = pd.read_csv("../data/centros_educativos.csv", sep=';', encoding='utf-8')

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

with sync_playwright() as p:
    browser = p.chromium.launch(headless=False)
    page = browser.new_page()

    for codigo in codigos_a_buscar:
        url = f"https://gestiona.comunidad.madrid/wpad_pub/run/j/MostrarFichaCentro.icm?cdCentro={codigo}"

        try:
            page.goto(url, timeout=20000)
            page.wait_for_timeout(1000)

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

                try:
                    page.get_by_text("RESULTADOS ACADÉMICOS", exact=False).first.click(force=True)
                    page.wait_for_timeout(1500)
                except:
                    pass

                datos["Nota_EvAU"] = hacer_clic_y_leer(page, "Nota media Bloque", "PAU", limpiar_nota)
                datos["Nota_Expediente"] = hacer_clic_y_leer(page, "Nota media del expediente", "PAU", limpiar_nota)
                datos["Present_EvAU"] = hacer_clic_y_leer(page, "alumnos presentados", "PAU", limpiar_entero)
                datos["Matric_EvAU"] = hacer_clic_y_leer(page, "matriculados", "PAU", limpiar_entero)

                try:
                    page.locator("label:has-text('ESO')").first.click(force=True, timeout=1000)
                except:
                    pass
                datos["%_Titulacion_ESO"] = hacer_clic_y_leer(page, "que titula", "SECUNDARIA", limpiar_porcentaje)

                try:
                    page.locator("label:has-text('Bachillerato')").first.click(force=True, timeout=1000)
                except:
                    pass
                datos["Matric_Bach"] = hacer_clic_y_leer(page, "matriculados", "BACHILLERATO", limpiar_entero)

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
            else:
                print(f"[{contador}/{total}] Descartado (No tiene horario de tarde)")

        except Exception as e:
            print(f"[{contador}/{total}] ❌ Error conectando a la web")

        contador += 1

    browser.close()

print("\n3. Guardando Excel final...")
if len(resultados) > 0:
    df_resultados = pd.DataFrame(resultados)
    # Guardamos en la carpeta outputs
    df_resultados.to_csv("../outputs/Institutos_Sur_Extraccion_Clics.csv", index=False, encoding='utf-8-sig', sep=';')
    print("¡Éxito! Archivo generado.")
