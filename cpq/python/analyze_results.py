#!/usr/bin/env python3
'''Dashboard voor combinatie-resultaten. Gebruik: streamlit run analyze_results_combinaties.py'''
from __future__ import annotations
import importlib.util
import json
import sys
from pathlib import Path
from typing import Any
import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

RESULTS_DIR = Path('test_results')
ENGINE_PATH = Path(__file__).resolve().parent / 'test.py'
GREEN, LIGHT, RED = '#173F35', '#EAF3EF', '#B94A48'
COLORS = ['#4C78A8','#F58518','#54A24B','#E45756','#72B7B2','#B279A2']
st.set_page_config(page_title='ServiceSets Combinaties', page_icon='📦', layout='wide')
st.markdown(f'''<style>
.stApp{{background:#F7F8F7}} [data-testid="stSidebar"]{{background:{GREEN}}} [data-testid="stSidebar"] *{{color:white!important}}
.header{{padding:26px 32px;border-radius:16px;background:{GREEN};color:white;margin-bottom:18px}} .header h1{{margin:0}}
.card{{background:white;border:1px solid #E4EAE7;border-radius:14px;padding:16px}} .label{{color:#66736F;font-size:.8rem;font-weight:700;text-transform:uppercase}} .value{{color:{GREEN};font-size:1.8rem;font-weight:800}}
.section{{color:{GREEN};font-size:1.3rem;font-weight:800;margin:24px 0 10px}} .info{{background:{LIGHT};border-left:5px solid #D6A85F;padding:12px 16px;border-radius:8px}}
</style>''', unsafe_allow_html=True)

def load_json(path: Path, default: Any):
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except (OSError, json.JSONDecodeError):
        return default

def dim_text(d: Any) -> str:
    if not isinstance(d, dict): return '—'
    l,w,h = d.get('lengte',d.get('l')),d.get('breedte',d.get('w')),d.get('hoogte',d.get('h'))
    return f'{l:g} × {w:g} × {h:g} cm' if None not in (l,w,h) else '—'

def reason(value: Any) -> str:
    return {'ITEMS_DID_NOT_ALL_FIT':'Niet alle items passen','PACKING_ENGINE_ERROR':'Fout in de packing engine','WEIGHT_LIMIT':'Gewichtslimiet overschreden'}.get(str(value or ''),str(value or ''))

def normalise(raw: Any):
    scenarios, details = [], []
    for s in raw if isinstance(raw,list) else []:
        if not isinstance(s,dict): continue
        items=s.get('items') or []
        text=', '.join(f"{i.get('product_name',i.get('product_id','?'))} ×{i.get('quantity',1)}" for i in items)
        results=s.get('results_per_package') or []
        passing=[r for r in results if r.get('status')=='PASS']
        scenarios.append({'id':s.get('scenario_id',''),'naam':s.get('scenario_name','Onbekende combinatie'),'categorie':s.get('category') or '—','omschrijving':s.get('description') or '','items':text,'artikelen':s.get('distinct_articles',len(items)),'stuks':s.get('total_quantity',sum(i.get('quantity',1) for i in items)),'past':bool(s.get('fits_any_package',passing)),'kleinste':s.get('smallest_fitting_package') or '—','passend':len(passing),'getest':len(results),'percentage':round(100*len(passing)/len(results),1) if results else 0})
        for r in results:
            details.append({'naam':s.get('scenario_name','Onbekende combinatie'),'items':text,'package':r.get('package','—'),'afmetingen':dim_text(r.get('package_dimensions_cm')),'raw_dims':r.get('package_dimensions_cm') or {},'status':str(r.get('status','')).upper(),'volume':r.get('volume_pct'),'gewicht':r.get('total_weight_g'),'past_items':r.get('fitted_count',0),'niet_past_items':r.get('unfitted_count',0),'reden':reason(r.get('reason')),'plaatsingen':r.get('placements') or [],'gestapeld':(r.get('stacked_articles') or {}).get('details') or [],'gevouwen':(r.get('folded_articles') or {}).get('details') or []})
    d=pd.DataFrame(details)
    for c in ('volume','gewicht'):
        if c in d: d[c]=pd.to_numeric(d[c],errors='coerce')
    return pd.DataFrame(scenarios),d

def card(label,value): st.markdown(f'<div class="card"><div class="label">{label}</div><div class="value">{value}</div></div>',unsafe_allow_html=True)

def add_box(fig,pos,size,color,name):
    x0,y0,z0=map(float,pos); dx,dy,dz=map(float,size)
    x=[x0,x0,x0+dx,x0+dx,x0,x0,x0+dx,x0+dx];y=[y0,y0+dy,y0+dy,y0,y0,y0+dy,y0+dy,y0];z=[z0,z0,z0,z0,z0+dz,z0+dz,z0+dz,z0+dz]
    fig.add_trace(go.Mesh3d(x=x,y=y,z=z,i=[7,0,0,0,4,4,6,6,4,0,3,2],j=[3,4,1,2,5,6,5,2,0,1,6,3],k=[0,7,2,3,6,7,1,1,5,5,7,6],color=color,opacity=.75,name=name,hovertext=name,hoverinfo='text'))

def plot_packing(d,placements,title):
    l,w,h=(float(d.get(k,0)) for k in ('lengte','breedte','hoogte')); fig=go.Figure()
    e=[(0,0,0),(l,0,0),(l,w,0),(0,w,0),(0,0,0),(0,0,h),(l,0,h),(l,0,0),(l,0,h),(l,w,h),(l,w,0),(l,w,h),(0,w,h),(0,w,0),(0,w,h),(0,0,h)];x,y,z=zip(*e)
    fig.add_trace(go.Scatter3d(x=x,y=y,z=z,mode='lines',line=dict(color='black',width=4),name='Verpakking'))
    palette={}
    for p in placements:
        pid=str(p.get('product_id','?')); palette.setdefault(pid,COLORS[len(palette)%len(COLORS)])
        add_box(fig,p.get('position',[0,0,0]),p.get('dimensions',[0,0,0]),palette[pid],p.get('product_name',pid))
    fig.update_layout(title=title,template='plotly_white',height=560,margin=dict(l=0,r=0,t=48,b=0),scene=dict(xaxis_title='Lengte (cm)',yaxis_title='Breedte (cm)',zaxis_title='Hoogte (cm)',aspectmode='data'))
    return fig

@st.cache_resource(show_spinner=False)
def engine():
    if not ENGINE_PATH.exists(): return None
    spec=importlib.util.spec_from_file_location('ss_engine',ENGINE_PATH)
    if not spec or not spec.loader: return None
    module=importlib.util.module_from_spec(spec);sys.modules[spec.name]=module;spec.loader.exec_module(module);return module

st.markdown('<div class="header"><h1>ServiceSets – Combinatieanalyse</h1><p>Service-sets en ad-hoc combinaties, zonder individuele producttests.</p></div>',unsafe_allow_html=True)
scenarios,details=normalise(load_json(RESULTS_DIR/'all_results.json',[]))
problems=load_json(RESULTS_DIR/'data_problems.json',[])
if scenarios.empty:
    st.error('Geen resultaten in test_results/all_results.json.');st.info('Voer eerst python tester_combinaties.py uit.');st.stop()

st.sidebar.markdown('## Filters')
cats=sorted(scenarios['categorie'].unique()); chosen=st.sidebar.multiselect('Categorie',cats); query=st.sidebar.text_input('Zoek combinatie of artikel')
view=scenarios.copy()
if chosen:view=view[view['categorie'].isin(chosen)]
if query:
    q=query.lower();view=view[view['naam'].str.lower().str.contains(q,na=False)|view['items'].str.lower().str.contains(q,na=False)]
c1,c2,c3,c4=st.columns(4)
with c1:card('Combinaties',str(len(view)))
with c2:card('Passen ergens',str(int(view['past'].sum())))
with c3:card('Passen nergens',str(int((~view['past']).sum())))
with c4:card('Gem. passpercentage',f"{view['percentage'].mean():.1f}%".replace('.',','))
st.markdown('<div class="info">Alle artikelen en aantallen worden <strong>samen</strong> in één verpakking getest.</div>',unsafe_allow_html=True)
tab1,tab2,tab3,tab4=st.tabs(['Overzicht','Per combinatie','Zelf samenstellen','Dataproblemen'])
with tab1:
    st.markdown('<div class="section">Combinatie-overzicht</div>',unsafe_allow_html=True)
    table=view[['naam','categorie','items','artikelen','stuks','kleinste','passend','getest','percentage','past']].rename(columns={'naam':'Combinatie','categorie':'Categorie','items':'Artikelen × aantallen','artikelen':'Verschillende artikelen','stuks':'Totaal stuks','kleinste':'Kleinste passende verpakking','passend':'Passende verpakkingen','getest':'Getest','percentage':'Pass %','past':'Past ergens?'})
    st.dataframe(table,width='stretch',hide_index=True,height=min(650,80+42*len(table)))
    st.download_button('Download overzicht als CSV',table.to_csv(index=False).encode('utf-8'),'servicesets_combinaties.csv','text/csv')
    fig=px.bar(view.sort_values('percentage'),x='percentage',y='naam',orientation='h',color='categorie',text='percentage',title='Passpercentage per combinatie');fig.update_traces(texttemplate='%{text:.1f}%');fig.update_layout(template='plotly_white',height=max(340,45*len(view)),xaxis_title='Passpercentage',yaxis_title='');st.plotly_chart(fig,width='stretch')
    for _,row in view[~view['past']].iterrows():st.warning(f"{row['naam']} — {row['stuks']} stuks: {row['items']}")
with tab2:
    name=st.selectbox('Kies een combinatie',view['naam'].tolist()); picked=details[details['naam']==name].copy()
    if picked.empty:st.info('Geen details beschikbaar.')
    else:
        st.caption(picked['items'].iloc[0])
        display=picked[['package','afmetingen','status','volume','gewicht','past_items','niet_past_items','reden']].rename(columns={'package':'Verpakking','afmetingen':'Afmetingen','status':'Resultaat','volume':'Volume %','gewicht':'Totaalgewicht g','past_items':'Items passen','niet_past_items':'Items passen niet','reden':'Reden'})
        st.dataframe(display,width='stretch',hide_index=True)
        yes=picked[picked['status']=='PASS']['package'].tolist(); pkg=st.selectbox('Visualiseer verpakking',picked['package'].tolist(),format_func=lambda x:f'✓ {x}' if x in yes else f'✗ {x} (past niet)')
        row=picked[picked['package']==pkg].iloc[0]
        if row['plaatsingen']:st.plotly_chart(plot_packing(row['raw_dims'],row['plaatsingen'],f'{name} in {pkg}'),width='stretch')
        else:st.warning('Geen geplaatste artikelen voor deze verpakking.')
        if row['gestapeld']:st.markdown('<div class="section">Gestapelde artikelen</div>',unsafe_allow_html=True);st.dataframe(pd.DataFrame(row['gestapeld']),width='stretch',hide_index=True)
        if row['gevouwen']:st.markdown('<div class="section">Gevouwen artikelen</div>',unsafe_allow_html=True);st.dataframe(pd.DataFrame(row['gevouwen']),width='stretch',hide_index=True)
with tab3:
    e = engine()

    if e is None:
        st.warning(
            'Plaats test.py naast dit dashboard om zelf combinaties te testen.'
        )
    else:
        try:
            pr = (
                e.load_json_file(Path('data/products.json'))
                if Path('data/products.json').exists()
                else e.download_json(e.PRODUCTS_URL)
            )

            pa = (
                e.load_json_file(Path('data/package_dimensions.json'))
                if Path('data/package_dimensions.json').exists()
                else e.download_json(e.PACKAGES_URL)
            )

            products, _ = e.load_products(pr)
            packages, _ = e.load_packages(pa)

            labels = {
                f'{p.name} ({p.product_id})': p
                for p in products
            }

            selected = st.multiselect(
                'Artikelen',
                sorted(labels)
            )

            expanded = []

            for label in selected:
                p = labels[label]

                count = st.number_input(
                    label,
                    min_value=1,
                    max_value=999,
                    value=1,
                    key=f'amount_{p.product_id}'
                )

                expanded.extend([p] * int(count))

            if st.button('Test combinatie', type='primary') and expanded:

                # Test de combinatie in alle verpakkingen
                results = [
                    e.test_products_together(expanded, p)
                    for p in sorted(packages, key=lambda x: x.volume)
                ]

                # Overzichtstabel
                result_rows = [
                    {
                        'Verpakking': r['package'],
                        'Resultaat': r['status'],
                        'Volume %': r['volume_pct'],
                        'Items passen': r['fitted_count'],
                        'Items passen niet': r['unfitted_count'],
                    }
                    for r in results
                ]

                st.dataframe(
                    pd.DataFrame(result_rows),
                    width='stretch',
                    hide_index=True
                )

                # -----------------------------------------
                # 3D WEERGAVE
                # -----------------------------------------

                st.markdown(
                    '<div class="section">3D-weergave</div>',
                    unsafe_allow_html=True
                )

                package_names = [
                    r['package']
                    for r in results
                ]

                passing_packages = {
                    r['package']
                    for r in results
                    if r.get('status') == 'PASS'
                }

                selected_package = st.selectbox(
                    'Visualiseer verpakking',
                    package_names,
                    format_func=lambda x: (
                        f'✓ {x}'
                        if x in passing_packages
                        else f'✗ {x} (past niet)'
                    ),
                    key='custom_combination_package'
                )

                selected_result = next(
                    r for r in results
                    if r['package'] == selected_package
                )

                raw_dims = selected_result.get(
                    'package_dimensions_cm',
                    {}
                )

                placements = selected_result.get(
                    'placements',
                    []
                )

                if raw_dims and placements:
                    st.plotly_chart(
                        plot_packing(
                            raw_dims,
                            placements,
                            f'Zelf samengestelde combinatie in {selected_package}'
                        ),
                        width='stretch'
                    )
                elif raw_dims:
                    st.warning(
                        'De verpakking is beschikbaar, maar er zijn geen '
                        'plaatsingen beschikbaar voor de 3D-weergave.'
                    )
                else:
                    st.warning(
                        'Geen verpakkingsafmetingen beschikbaar voor '
                        'de 3D-weergave.'
                    )

                # -----------------------------------------
                # GESTAPELDE ARTIKELEN
                # -----------------------------------------

                stacked = (
                    selected_result.get('stacked_articles') or {}
                ).get('details') or []

                if stacked:
                    st.markdown(
                        '<div class="section">Gestapelde artikelen</div>',
                        unsafe_allow_html=True
                    )

                    st.dataframe(
                        pd.DataFrame(stacked),
                        width='stretch',
                        hide_index=True
                    )

                # -----------------------------------------
                # GEVOUWEN ARTIKELEN
                # -----------------------------------------

                folded = (
                    selected_result.get('folded_articles') or {}
                ).get('details') or []

                if folded:
                    st.markdown(
                        '<div class="section">Gevouwen artikelen</div>',
                        unsafe_allow_html=True
                    )

                    st.dataframe(
                        pd.DataFrame(folded),
                        width='stretch',
                        hide_index=True
                    )

        except Exception as exc:
            st.error(
                f'Kon catalogus of packing engine niet laden: {exc}'
            )

with tab4:
    st.dataframe(pd.DataFrame(problems),width='stretch',hide_index=True) if problems else st.success('Geen dataproblemen gevonden.')
st.caption('ServiceSets.com · gebaseerd op all_results.json')
