import streamlit as st
from pymongo import MongoClient
import pandas as pd

# ─── Configuración de página ───
st.set_page_config(page_title="Clientes Banco Andino", page_icon="👤", layout="wide")

st.title("👤 Búsqueda de Clientes — Sample Analytics")
st.caption("Consulta clientes, sus cuentas y transacciones asociadas vía MongoDB Atlas")

# ─── Conexión a MongoDB Atlas vía secrets ───
try:
    mongo_uri = st.secrets["mongo"]["uri"]
except KeyError:
    st.error(
        "❌ No se encontró el secreto `mongo.uri`. "
        "Crea el archivo `.streamlit/secrets.toml` con:\n\n"
        "```toml\n[mongo]\nuri = \"mongodb+srv://usuario:password@cluster.xxxxx.mongodb.net/\"\n```"
    )
    st.stop()

with st.sidebar:
    st.header("🔌 MongoDB Atlas")
    st.markdown(
        "**Conexión:** vía `st.secrets`\n\n"
        "**Base de datos:** `sample_analytics`\n"
        "**Colecciones:**\n"
        "- `customers`\n"
        "- `accounts`\n"
        "- `transactions`"
    )

# ─── Conectar ───
@st.cache_resource
def get_client(uri):
    return MongoClient(uri)

try:
    client = get_client(mongo_uri)
    db = client["sample_analytics"]
    col_customers = db["customers"]
    col_accounts = db["accounts"]
    col_transactions = db["transactions"]

    client.admin.command("ping")
    st.sidebar.success("✅ Conectado a MongoDB Atlas")
except Exception as e:
    st.error(f"❌ Error de conexión: {e}")
    st.stop()

# ─── Búsqueda ───
st.markdown("---")
col1, col2 = st.columns([3, 1])

with col1:
    texto_busqueda = st.text_input(
        "🔍 Buscar cliente por username, nombre o email",
        placeholder="Ej: valenciajennifer, Lindsay, hotmail"
    )

with col2:
    limite = st.selectbox("Resultados máx.", [5, 10, 20, 50], index=1)

if not texto_busqueda:
    st.info("Escribe un username, nombre o email para buscar clientes.")
    st.stop()

# ─── Consulta de clientes ───
query = {
    "$or": [
        {"username": {"$regex": texto_busqueda, "$options": "i"}},
        {"name": {"$regex": texto_busqueda, "$options": "i"}},
        {"email": {"$regex": texto_busqueda, "$options": "i"}}
    ]
}

clientes = list(col_customers.find(query).limit(limite))

if not clientes:
    st.warning(f"No se encontraron clientes con **'{texto_busqueda}'**.")
    st.stop()

st.success(f"Se encontraron **{len(clientes)}** cliente(s)")

# ─── Construir tabla de resultados ───
resultados = []

for c in clientes:
    cuentas_cliente = c.get("accounts", [])
    total_cuentas = len(cuentas_cliente)

    # Buscar documentos de cuentas asociados
    cuentas_docs = list(col_accounts.find({"account_id": {"$in": cuentas_cliente}}))

    total_limite = sum(acc.get("limit", 0) for acc in cuentas_docs)
    productos = []
    for acc in cuentas_docs:
        productos.extend(acc.get("products", []))

    # Buscar transacciones asociadas
    transacciones_docs = list(col_transactions.find({"account_id": {"$in": cuentas_cliente}}))
    total_buckets = len(transacciones_docs)
    total_transacciones = sum(t.get("transaction_count", 0) for t in transacciones_docs)

    resultados.append({
        "Username": c.get("username", "—"),
        "Nombre": c.get("name", "—"),
        "Email": c.get("email", "—"),
        "Dirección": c.get("address", "—"),
        "Cumpleaños": str(c.get("birthdate", "—"))[:10],
        "N° Cuentas": total_cuentas,
        "Límite Total": total_limite,
        "Productos": ", ".join(sorted(set(productos))) if productos else "—",
        "Buckets Transacciones": total_buckets,
        "Total Transacciones": total_transacciones
    })

df = pd.DataFrame(resultados)

# ─── Mostrar tabla ───
st.markdown("### 📋 Resultados")
st.dataframe(df, use_container_width=True, hide_index=True)

# ─── Detalle expandible por cliente ───
st.markdown("### 📝 Detalle por cliente")

for c in clientes:
    username = c.get("username", "—")
    nombre = c.get("name", "—")
    email = c.get("email", "—")
    cuentas_cliente = c.get("accounts", [])

    cuentas_docs = list(col_accounts.find({"account_id": {"$in": cuentas_cliente}}))
    transacciones_docs = list(col_transactions.find({"account_id": {"$in": cuentas_cliente}}))

    with st.expander(f"**{nombre}** — {username} ({email})"):
        c1, c2 = st.columns(2)

        with c1:
            st.markdown(f"**Nombre:** {nombre}")
            st.markdown(f"**Username:** {username}")
            st.markdown(f"**Email:** {email}")
            st.markdown(f"**Dirección:** {c.get('address', '—')}")
            st.markdown(f"**Cumpleaños:** {str(c.get('birthdate', '—'))[:10]}")
            st.markdown(f"**Cuentas asociadas:** {len(cuentas_cliente)}")

            if "tier_and_details" in c:
                st.markdown("**Tier y detalles:**")
                st.json(c["tier_and_details"])

        with c2:
            if cuentas_docs:
                cuentas_data = []
                for acc in cuentas_docs:
                    cuentas_data.append({
                        "Account ID": acc.get("account_id", "—"),
                        "Límite": acc.get("limit", "—"),
                        "Productos": ", ".join(acc.get("products", []))
                    })

                st.markdown("**Cuentas del cliente:**")
                st.dataframe(pd.DataFrame(cuentas_data), hide_index=True, use_container_width=True)
            else:
                st.info("No se encontraron cuentas asociadas.")

        st.markdown("---")

        if transacciones_docs:
            resumen_transacciones = []
            for t in transacciones_docs:
                resumen_transacciones.append({
                    "Account ID": t.get("account_id", "—"),
                    "Transaction Count": t.get("transaction_count", 0),
                    "Inicio": str(t.get("bucket_start_date", "—"))[:10],
                    "Fin": str(t.get("bucket_end_date", "—"))[:10]
                })

            st.markdown("**Resumen de transacciones:**")
            st.dataframe(pd.DataFrame(resumen_transacciones), hide_index=True, use_container_width=True)

            # Mostrar detalle de transacciones internas
            for t in transacciones_docs[:5]:
                with st.expander(f"Ver transacciones de cuenta {t.get('account_id', '—')}"):
                    transacciones_lista = t.get("transactions", [])

                    if transacciones_lista:
                        detalle_trans = []
                        for mov in transacciones_lista[:20]:
                            detalle_trans.append({
                                "Fecha": str(mov.get("date", "—"))[:10],
                                "Monto": mov.get("amount", "—"),
                                "Código": mov.get("transaction_code", "—"),
                                "Símbolo": mov.get("symbol", "—"),
                                "Precio": mov.get("price", "—"),
                                "Total": mov.get("total", "—")
                            })

                        st.dataframe(pd.DataFrame(detalle_trans), hide_index=True, use_container_width=True)
                    else:
                        st.info("No hay transacciones registradas en este documento.")
        else:
            st.info("No se encontraron transacciones asociadas.")