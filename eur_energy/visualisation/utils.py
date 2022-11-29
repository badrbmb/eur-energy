def hide_footer():
    # hide streamlit footer (if needed?)
    import streamlit as st
    hide_streamlit_style = """
                <style>
                #MainMenu {visibility: hidden;}
                footer {visibility: hidden;}
                </style>
                """
    st.markdown(hide_streamlit_style, unsafe_allow_html=True)


def switch_page(page_name: str, main="🏠_Home.py"):
    """
    switch pages in multi-page app
    adapted from arnaudmiribel/streamlit-extras
    reference: https://github.com/arnaudmiribel/streamlit-extras/blob/main/src/streamlit_extras/switch_page_button/__init__.py
    Args:
        page_name: the target page name to witch to
        main: the basename of the file containing main streamlit app
    Returns:
    """
    from streamlit.runtime.scriptrunner import RerunData, RerunException
    from streamlit.source_util import get_pages

    def standardize_name(name: str) -> str:
        return name.lower().replace("_", " ")

    page_name = standardize_name(page_name)

    pages = get_pages(main)

    for page_hash, config in pages.items():
        if standardize_name(config["page_name"]) == page_name:
            raise RerunException(
                RerunData(
                    page_script_hash=page_hash,
                    page_name=page_name,
                )
            )

    page_names = [standardize_name(config["page_name"]) for config in pages.values()]

    raise ValueError(f"Could not find page {page_name}. Must be one of {page_names}")


def generate_card(wch_colour_box=(255, 255, 255), title_colour_font=(0, 0, 0), subtitle_colour_font=(0, 0, 0),
                  title_font_size=18, subtitle_font_size=14, opacity=1,
                  icon_name="fas fa-asterisk", icon_size='fa-2xl', title="Title", subtitle='Subtitle'):
    """
    Generate a box element in html with the specified CSS properties
    Args:
        wch_colour_box:
        title_colour_font:
        subtitle_colour_font:
        title_font_size:
        subtitle_font_size:
        opacity:
        icon_name:
        icon_size:
        title:
        subtitle:
    Returns:

    """
    # link pointing to font awesome icons
    lnk = '<link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/6.2.0/css/all.min.css" crossorigin="anonymous">'
    # populate html element
    htmlstr = f"""<p style='background-color: rgb({wch_colour_box[0]}, 
                                                  {wch_colour_box[1]}, 
                                                  {wch_colour_box[2]}, {opacity}); 
                            color: rgb({title_colour_font[0]}, 
                                       {title_colour_font[1]}, 
                                       {title_colour_font[2]}, {opacity}); 
                            font-size: {title_font_size}px; 
                            border-radius: 7px; 
                            padding-left: 12px; 
                            padding-top: 18px; 
                            padding-bottom: 18px; 
                            line-height:25px;'>
                            <i class='{icon_name} {icon_size}'; 
                            color: rgb({subtitle_colour_font[0]}, 
                                       {subtitle_colour_font[1]}, 
                                       {subtitle_colour_font[2]}, {opacity})></i>
                            </style>
                            <BR>
                            <BR>
                            <span style='color: rgb({title_colour_font[0]}, 
                                       {title_colour_font[1]}, 
                                       {title_colour_font[2]}, {opacity}); 
                            font-size: {title_font_size}px;'>{title}</span>
                            <BR>
                            <span style='font-size: {subtitle_font_size}px; 
                            margin-top: 0;
                            color: rgb({subtitle_colour_font[0]}, 
                                       {subtitle_colour_font[1]}, 
                                       {subtitle_colour_font[2]}, {opacity}); 
                            '>{subtitle}</span></p>"""

    return lnk + htmlstr


CONTACT_EMAIL = 'badr.benb@gmail.com'
