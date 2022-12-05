import re

import numpy as np
from millify import millify
from plotly import express as px, graph_objects as go

from eur_energy.model.countries import Country
from eur_energy.visualisation.utils import generate_multiplier_prefixes

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

COLOR_DICT_SUB_SECTORS = {
    'Chemicals Industry': '#636EFA',
    'Iron and steel': '#EF553B',
    'Non Ferrous Metals': '#00CC96',
    'Non-metallic mineral products': '#AB63FA',
    'Pulp, paper and printing': '#FFA15A'
}


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
    # drop country with no production
    df_stats = df_stats[df_stats['Physical output (tonne)'] > 0].copy()
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
            opacity=0.9,
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
            opacity=0.9,
            font=dict(color="#2e2f31"),
            arrowcolor="#9b9b9b",
        )

    return fig


def generate_country_fuel_demand(df_fuel_demand, exclude_null=True):
    df_plot = df_fuel_demand.copy()
    if exclude_null:
        df_plot = df_plot[df_fuel_demand['value'] > 0]
    # reformat share
    df_plot['share'] = df_plot['share'].apply(lambda x: f"{round(x * 100, 2)}%")
    fig = px.sunburst(
        df_plot, path=['fuel_class', 'fuel'], values='value', hover_data=['unit', 'share'],
    )
    fig.update_traces(insidetextorientation='radial')
    fig.update_layout(
        margin={"r": 0, "t": 0, "l": 0, "b": 0},
    )
    return fig


def generate_country_demand_by_sub_sector(df_fuel_demand_sub_sector):
    fig = px.pie(df_fuel_demand_sub_sector, names='sub_sector', values='value', hover_data=['unit'],
                 color='sub_sector', color_discrete_map=COLOR_DICT_SUB_SECTORS)
    fig.update_layout(
        margin={"r": 0, "t": 0, "l": 0, "b": 0},
        legend=dict(orientation='h')
    )
    return fig


def generate_emission_intensities_by_sub_sector(df_efs):
    # add text
    df_efs['text'] = round(df_efs['value'])
    fig = px.bar(df_efs, x='sub_sector', y='value', hover_data=['unit'], text='text', color='sub_sector',
                 color_discrete_map=COLOR_DICT_SUB_SECTORS)
    fig.update_layout(
        yaxis=dict(title='Total emission intensity (kgCO2/tonne)'),
        xaxis=dict(title=''),
        showlegend=False
    )
    return fig


def generate_country_emissions_by_sub_sector(df_emissions):
    # covert to mt and add metadata
    df_emissions['value'] = df_emissions['value'] / 1e9
    df_emissions['unit'] = 'mtCO2'
    df_emissions['share'] = round(df_emissions['value'] * 100 / df_emissions['value'].sum(), 1)

    df_emissions['text'] = df_emissions.apply(lambda x: f"{x['sub_sector']} ({x['share']}%)", axis=1)
    fig = px.icicle(
        df_emissions,
        path=[px.Constant("Industry"), 'sub_sector'], hover_data=['unit'],
        values='value', color='sub_sector', custom_data=['share'],
        color_discrete_map=COLOR_DICT_SUB_SECTORS
    )
    fig.update_traces(
        texttemplate="%{label}: %{value:.2f} mtCO2 <br>(%{customdata[0]}%)",
    )
    fig.update_layout(
        margin={"r": 0, "t": 0, "l": 0, "b": 0},
    )
    return fig


def generate_sub_sector_summary_plot(df_plot, variable):
    # get unit
    _unit = df_plot['unit'].values[0]

    # add text using "millified" values
    def _format_text(x, unit):
        try:
            _multiplier, _prefixes = generate_multiplier_prefixes(unit)
            if len(str(int(x))) >= 4:
                # means it does need a multiplier:
                return millify(x * _multiplier, prefixes=_prefixes, precision=2)
            else:
                return f"{round(x, 1)} {unit}"
        except NotImplementedError:
            # must be percentage
            return f"{round(x, 2)}%"

    df_plot['text'] = df_plot['value'].apply(lambda x: _format_text(x, unit=_unit))
    fig = px.bar(df_plot, x='process', y='value', color='process', text='text')
    fig.update_layout(
        showlegend=False,
        yaxis=dict(title=f'{variable}'),
        margin={"r": 0, "t": 0, "l": 0, "b": 0},
        plot_bgcolor='rgba(0,0,0,0)'
    )
    fig.update_xaxes(showline=True, linewidth=2, linecolor='#d6d6d6', title='Process')
    fig.update_yaxes(
        showgrid=False, zeroline=False,
        showline=True, linewidth=2, linecolor='#d6d6d6',
        showticklabels=False,
    )
    return fig


def generate_process_details_graph(data, variable, rounding, unit):
    # store waterfall values
    _values = [t['value'] for t in data] + [0]
    _names = [t['category'] for t in data] + ["Total"]
    _measure = ['relative'] * len(_values[:-1]) + ['total']
    _text = [round(t, rounding) for t in _values[:-1]] + [round(sum(_values), rounding)]

    # create waterfall chart
    fig = go.Figure(
        go.Waterfall(
            orientation="v",
            measure=_measure,
            x=_names,
            textposition="outside",
            text=_text,
            y=_values,
            decreasing={"marker": {"color": "#29bfb1"}},
            increasing={"marker": {"color": "#dc3444"}},
            connector={"line": {"color": "rgb(63, 63, 63)"}},
        )
    )

    fig.update_layout(
        yaxis=dict(title=f"{variable} ({unit}"),
        height=550,
        margin={"r": 0, "t": 0, "l": 0, "b": 0},
    )

    return fig
