from flask import Flask, render_template_string
import folium
import pandas as pd


app = Flask(__name__)


@app.route('/')
def index():
    # Coordinates for Manhattan (approximate center)
    manhattan_coords = [40.7831, -73.9712]

    # Create a map centered on Manhattan
    map_obj = folium.Map(location=manhattan_coords, zoom_start=12)

    # Generate the HTML representation of the map
    map_html = map_obj._repr_html_()

    # Render the map in a simple HTML template
    html_template = """
    <!doctype html>
    <html>
      <head>
        <meta charset="utf-8">
        <title>Manhattan Map</title>
      </head>
      <body>
        <h1>Map of Manhattan</h1>
        {{ map_html|safe }}
      </body>
    </html>
    """
    return render_template_string(html_template, map_html=map_html)


if __name__ == '__main__':
    
    app.run(debug=True)
    

