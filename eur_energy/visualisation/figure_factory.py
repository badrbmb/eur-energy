import re

import numpy as np
from plotly import express as px, graph_objects as go

from eur_energy.model.countries import Country


def generate_heatmap(df_map, variable_to_show, country_borders, process):
    df_show_map = df_map[
        (df_map['variable'] == variable_to_show) &
        # exclude EU28
        (df_map['iso2'] != 'EU28')
        ].copy()

    unit = df_show_map['unit'].values[0]

    fig = px.choropleth_mapbox(
        df_show_map, geojson=country_borders, color="value",
        animation_frame="year",
        mapbox_style="carto-positron",
        color_continuous_scale='Reds',
        zoom=2.2, center={"lon": 5.8849601082954734, "lat": 55.37918894782564},  # roughly center of europe
        locations="iso2", featureidkey="properties.FID",
        hover_data=["country", "sub_sector", "process", 'variable', 'unit'],
        labels={'value': f"<b>{process}</b><br>{variable_to_show}<br>({unit})"},
        range_color=(min(df_show_map['value']), max(df_show_map['value']))
    )

    fig.update_geos(fitbounds="locations", visible=False)
    fig.update_layout(
        margin={"r": 0, "t": 0, "l": 0, "b": 0},
        coloraxis_colorbar_x=0.05,
        coloraxis_colorbar_bgcolor="rgba(155,155,155, .5)",
        height=600,
    )

    return fig


def generate_cumulative_chart(df_data, reference_year, variable_to_show, colors_dict, add_annotations=True):
    df_stats = df_data[
        (df_data['year'] == reference_year) &
        (df_data['variable'].isin(['Physical output', variable_to_show])) &
        # exclude EU28
        (df_data['iso2'] != 'EU28')
        ].copy()
    # append unit to each variable
    df_stats['variable'] = df_stats.apply(lambda x: f"{x['variable']} ({x['unit']})", axis=1)
    df_stats = df_stats.pivot('iso2', 'variable', 'value').reset_index()
    # convert physical output to Mt
    df_stats['Physical output (tonne)'] *= 1 / 1e6
    df_stats.rename(columns={'Physical output (tonne)': 'Physical output (million tonnes)'}, inplace=True)

    # assign colors by country
    df_stats['colour'] = df_stats['iso2'].replace(colors_dict)

    # assign country
    df_stats['country'] = df_stats['iso2'].apply(lambda x: Country(iso2=x).country_name)

    col_x = "Physical output (million tonnes)"
    col_y = f"{variable_to_show} (GJ/tonne)"
    # col_y = 'useful energy demand intensity (GJ/tonne)'
    col_y_unit = re.findall('\((.*?)\)', col_y)[0]

    # sort values
    df_stats.sort_values(col_y, ascending=True, inplace=True)

    # add cumulative column
    df_stats['cumsum'] = df_stats[col_x].cumsum()

    # get quantile 10%
    q10 = np.quantile(df_stats[col_y], q=.1)

    fig = go.Figure()

    fig.add_trace(
        go.Bar(
            x=df_stats['cumsum'] - df_stats[col_x],
            y=df_stats[col_y],
            width=df_stats[col_x],
            marker_color=df_stats["colour"],
            marker=dict(opacity=.8),
            offset=0,
            textposition="auto",
            text=df_stats["iso2"],
            textfont=dict(color="white"),
            customdata=df_stats[col_x],
            hovertext=df_stats['country'],
            hovertemplate="%{hovertext}<br>$VAR1: %{customdata:.2f}<br><extra>$VAR2 <br> %{y:.2f}</extra>".replace(
                '$VAR1', col_x).replace('$VAR2', col_y)
        )
    )

    fig.add_hline(
        y=q10, line=dict(color='red', dash='dot'),
        annotation_text=f"<b>Top 10% ~ {round(q10, 2)} {col_y_unit}</b>", annotation_position='bottom right',
        annotation=dict(bgcolor='white', opacity=.7, font=dict(color="#2e2f31")),
    )

    fig.update_layout(
        xaxis=dict(title=f"Cumulative {col_x.lower()}"),
        yaxis=dict(title=col_y.replace(' intensity', '')),
        margin={"r": 0, "t": 0, "l": 0, "b": 0},
    )

    if add_annotations:
        # add annotation biggest producer
        annotation_entry = df_stats[df_stats[col_x] == df_stats[col_x].max()].iloc[0].to_dict()
        fig.add_annotation(
            x=annotation_entry['cumsum'] - 0.5 * annotation_entry[col_x],
            ax=-60,
            ay=-70,
            y=annotation_entry[col_y],
            text=f"<b>{annotation_entry['country']}</b>, <b>the biggest producer in EU27 + UK</b>,<br>has a {col_y.replace(f'({col_y_unit})', '')}<br>of <b>{round(annotation_entry[col_y], 2)} {col_y_unit}</b>",
            showarrow=True,
            arrowhead=1,
            arrowsize=1.5,
            align='left',
            bgcolor="#e1e4e1",
            opacity=0.8,
            font=dict(color="#2e2f31"),
            arrowcolor="#9b9b9b",
        )

        # add annotation for bad performer versus q10
        last_entry = df_stats.iloc[-1].to_dict()
        last_entry['delta'] = round((last_entry[col_y] - q10) / q10 * 100, 2)

        fig.add_annotation(
            x=last_entry['cumsum'] - 0.5 * last_entry[col_x],
            ax=-200,
            ay=-20,
            y=last_entry[col_y],
            text=f"<b>{last_entry['country']}</b> {col_y.replace(f'({col_y_unit})', '')}<br>is <b>{round(last_entry['delta'])}% higher<br>than the top 10% countries</b> in EU27+UK",
            showarrow=True,
            arrowhead=1,
            arrowsize=1.5,
            align='left',
            bgcolor="#e1e4e1",
            opacity=0.8,
            font=dict(color="#2e2f31"),
            arrowcolor="#9b9b9b",
        )

    return fig


# colors by country
COLOR_DICT_ISO2 = {
    'AT': '#2E91E5',
    'BE': '#E15F99',
    'BG': '#1CA71C',
    'CY': '#FB0D0D',
    'CZ': '#DA16FF',
    'DE': '#222A2A',
    'DK': '#B68100',
    'EE': '#750D86',
    'EL': '#EB663B',
    'ES': '#511CFB',
    'EU28': '#00A08B',
    'EU27+UK': '#00A08B',
    'FI': '#FB00D1',
    'FR': '#FC0080',
    'HR': '#B2828D',
    'HU': '#6C7C32',
    'IE': '#778AAE',
    'IT': '#862A16',
    'LT': '#A777F1',
    'LU': '#620042',
    'LV': '#1616A7',
    'MT': '#DA60CA',
    'NL': '#6C4516',
    'PL': '#0D2A63',
    'PT': '#AF0038',
    'RO': '#2E91E5',
    'SE': '#E15F99',
    'SI': '#1CA71C',
    'SK': '#FB0D0D',
    'UK': '#DA16FF'
}
