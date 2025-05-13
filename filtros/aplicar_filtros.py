# Nombre del archivo: aplicar_filtros.py
import pandas as pd


def aplicar_filtros(
        df,
        filtro_fuente_lista,
        filtro_proceso,
        filtro_pais,
        filtro_industria,
        filtro_avatar,
        filtro_prospectador,
        filtro_invite_aceptada_simple,
        filtro_sesion_agendada,
        fecha_ini,
        fecha_fin,
        nombre_columna_fecha  # <--- PARÁMETRO NUEVO Y ESENCIAL
):
    df_filtrado = df.copy()

    if "¿Quién Prospecto?" in df_filtrado.columns:
        df_filtrado["¿Quién Prospecto?"] = df_filtrado[
            "¿Quién Prospecto?"].replace("", pd.NA)

    if filtro_fuente_lista and "– Todos –" not in filtro_fuente_lista:
        df_filtrado = df_filtrado[df_filtrado["Fuente de la Lista"].isin(
            filtro_fuente_lista)]

    if filtro_proceso and "– Todos –" not in filtro_proceso:
        df_filtrado = df_filtrado[df_filtrado["Proceso"].isin(filtro_proceso)]

    if filtro_pais and "– Todos –" not in filtro_pais:
        df_filtrado = df_filtrado[df_filtrado["Pais"].isin(filtro_pais)]

    if filtro_industria and "– Todos –" not in filtro_industria:
        df_filtrado = df_filtrado[df_filtrado["Industria"].isin(
            filtro_industria)]

    if filtro_avatar and "– Todos –" not in filtro_avatar:
        df_filtrado = df_filtrado[df_filtrado["Avatar"].isin(filtro_avatar)]

    if filtro_invite_aceptada_simple != "– Todos –":
        df_filtrado = df_filtrado[df_filtrado["¿Invite Aceptada?"].apply(
            lambda x: str(x).strip().lower(
            ) == filtro_invite_aceptada_simple.strip().lower())]

    # --- SECCIÓN DE FILTRADO DE FECHAS MODIFICADA ---
    if fecha_ini and fecha_fin and nombre_columna_fecha:  # Asegurarse que se pasó el nombre de la columna
        if nombre_columna_fecha in df_filtrado.columns:
            # Asegurar que la columna sea datetime
            if not pd.api.types.is_datetime64_any_dtype(
                    df_filtrado[nombre_columna_fecha]):
                df_filtrado[nombre_columna_fecha] = pd.to_datetime(
                    df_filtrado[nombre_columna_fecha], errors='coerce')

            # Aplicar filtro si la columna es de tipo fecha (después de posible conversión)
            if pd.api.types.is_datetime64_any_dtype(
                    df_filtrado[nombre_columna_fecha]):
                # Quitar la hora para comparar solo fechas (si fecha_ini/fin son solo date)
                df_filtrado = df_filtrado[
                    (df_filtrado[nombre_columna_fecha].dt.normalize().dt.date
                     >= fecha_ini)
                    & (df_filtrado[nombre_columna_fecha].dt.normalize().dt.date
                       <= fecha_fin)]
            else:
                # Opcional: advertir si la columna de fecha no pudo ser convertida
                # st.warning(f"La columna '{nombre_columna_fecha}' no es de tipo fecha y no se pudo filtrar.")
                pass
        else:
            # Opcional: advertir si la columna no existe
            # st.warning(f"La columna de fecha '{nombre_columna_fecha}' no se encontró en los datos.")
            pass
    # --- FIN DE SECCIÓN MODIFICADA ---

    if filtro_sesion_agendada != "– Todos –":
        df_filtrado = df_filtrado[df_filtrado["Sesion Agendada?"].apply(
            lambda x: str(x).strip().lower() == filtro_sesion_agendada.strip(
            ).lower())]

    if filtro_prospectador and "– Todos –" not in filtro_prospectador:
        df_filtrado = df_filtrado[df_filtrado["¿Quién Prospecto?"].isin(
            filtro_prospectador)]

    return df_filtrado
