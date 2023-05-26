import './style.css';
import 'ol-layerswitcher/dist/ol-layerswitcher.css';
import { Map, View } from 'ol';
import TileLayer from 'ol/layer/Tile';
import TileWMS from 'ol/source/TileWMS';
import ImageWMS from 'ol/source/ImageWMS';
import ImageLayer from 'ol/layer/Image';
import OSM from 'ol/source/OSM';
import * as olProj from 'ol/proj';
import { ScaleLine } from 'ol/control'
import LayerSwitcher from 'ol-layerswitcher';
import { Group } from 'ol/layer'
import Overlay from 'ol/Overlay.js'
import GeoJSON from 'ol/format/GeoJSON'
import { toLonLat } from 'ol/proj';

let suitabilityLayer = null;

const map = new Map({
  target: 'map',
  layers: [
    new TileLayer({
      source: new OSM() // Basemap using OpenStreetMap
    })
  ],
  view: new View({
    center: olProj.transform([-9.15, 38.75], 'EPSG:4326', 'EPSG:3857'), // center it on Lisbon
    extent: [-1032072.1137317438, 4675857.5686363075, -1005074.567785163, 4695990.873671545],
    zoom: 12.5,
    minZoom: 10.5,
    maxZoom: 14.5
  })
});

let scale = new ScaleLine({
  bar: true,
  steps: 4,
  text: true,
  minWidth: 120
})

map.addControl(scale);

// Need to make sure that the simbology is different for schools and metro stations in GeoServer,
// otherwise they are going to be rendered the same
const schools = new TileLayer({
  source: new TileWMS({
    url: 'http://localhost:8080/geoserver/wms',
    params: { 'LAYERS': 'csig:schools' },
    serverType: 'geoserver'
  }),
  title: 'Escolas',
  visible: false
});

const metro_stations = new TileLayer({
  source: new TileWMS({
    url: 'http://localhost:8080/geoserver/wms',
    params: { 'LAYERS': 'csig:metro_stations' },
    serverType: 'geoserver'
  }),
  title: 'Estações de metro',
  visible: false
});

const roads = new TileLayer({
  source: new TileWMS({
    url: 'http://localhost:8080/geoserver/wms',
    params: { 'LAYERS': 'csig:redeviaria' },
    serverType: 'geoserver'
  }),
  title: 'Estradas',
  visible: false
});

const studyarea = new TileLayer({
  source: new TileWMS({
    url: 'http://localhost:8080/geoserver/wms',
    params: { 'LAYERS': 'csig:studyarea' },
    serverType: 'geoserver'
  }),
  title: 'Lisboa',
  visible: true
});

const overlayGroup = new Group({
  title: 'Camadas',
  fold: 'open',
  layers: [schools, metro_stations, roads, studyarea]
});

const layerSwitcher = new LayerSwitcher({
  tipLabel: 'Camadas',
  startActive: true
});

map.addLayer(overlayGroup)
map.addControl(layerSwitcher);

// Popup
const popup = new Overlay({
  element: document.getElementById('popup'),
});
map.addOverlay(popup)

const element = popup.getElement();
map.on('click', async function (evt) {
  let infos = await getInfoFromSuitability(evt);
  // Get address information too
  var coord = toLonLat(evt.coordinate);
  infos.push(await reverseGeocode(coord));
  infos.reverse();

  let content = "";
  for (let info of infos) {
    content += "<p>" + info + "</p>"
  }
  popup.setPosition(evt.coordinate);
  let popover = bootstrap.Popover.getInstance(element);
  if (popover) {
    popover.dispose();
  }
  popover = new bootstrap.Popover(element, {
    animation: false,
    container: element,
    content: content,
    html: true,
    placement: 'top',
    title: 'Informação',
  });
  popover.show();
});

async function getInfoFromSuitability(evt) {
  let info = [];
  if (suitabilityLayer == null) {
    info.push("Recomendação ainda por obter! Preencha o formulário e clique no botão calcular aptidão.");
    return info;
  }

  const layerProps = suitabilityLayer.getProperties();
  const layerSource = suitabilityLayer.getSource();
  if (layerProps.visible == true && (layerSource instanceof TileWMS || layerSource instanceof ImageWMS)) {

    const infoUrl = layerSource.getFeatureInfoUrl(
      evt.coordinate,
      map.getView().getResolution(),
      'EPSG:3857',
      { 'INFO_FORMAT': 'application/json' }
    )
    if (infoUrl) {
      let response = await fetch(infoUrl);
      let finfo = await response.text();

      const format = new GeoJSON();
      const features = format.readFeatures(JSON.parse(finfo));
      if (features.length > 0) {
        let fproperties = features[0].getProperties();
        if (fproperties.GRAY_INDEX) {
          info.push('Recomendação: ' + fproperties.GRAY_INDEX)
        }
        else {
          info.push('Sem recomendações para esta zona.')
        }
      }
    }
  }


  return info;
}

const updateLegend = function (wmsSource, resolution) {
  const graphicUrl = wmsSource.getLegendUrl(resolution);
  document.getElementById('legendContainer').style.display = "block";
  const img = document.getElementById('legend');
  img.src = graphicUrl;
};

function updateMap(wmsInfo, map) {
  // Enable CORS on GeoServer first!
  // https://docs.geoserver.org/latest/en/user/production/container.html#enable-cors

  // Needed to use ImageWMS and not TileWMS, otherwise geoserver would lock the file in the backend.
  // This should not be a concern as each store is custom to the user, there should not be a performance penalty for this.
  const wmsSource = new ImageWMS({
    url: wmsInfo.url,
    params: { 'LAYERS': wmsInfo.layer },
    ratio: 1,
    serverType: 'geoserver',
    crossOrigin: 'anonymous'
  })

  suitabilityLayer = new ImageLayer({
    source: wmsSource,
    title: 'Carta de Aptidão'
  })

  overlayGroup.getLayers().push(suitabilityLayer)

  map.render();
  layerSwitcher.renderPanel();

  const resolution = map.getView().getResolution();
  updateLegend(wmsSource, resolution);
}

function wpsRequest(jsonData, map) {
  var GEOSERVER_URL = 'http://localhost:5000';
  var myHeaders = new Headers();
  myHeaders.append("Content-Type", "application/xml");
  myHeaders.append("Access-Control-Allow-Origin", "*") // Honestly, too much work to handle CORS, it's no fun
  var raw = '<?xml version="1.0" encoding="UTF-8"?>\
  <wps:Execute version="1.0.0" service="WPS"\
  xmlns:xsi="http://www.w3.org/2001/XMLSchema-instance"\
  xmlns="http://www.opengis.net/wps/1.0.0"\
  xmlns:wfs="http://www.opengis.net/wfs"\
  xmlns:wps="http://www.opengis.net/wps/1.0.0"\
  xmlns:ows="http://www.opengis.net/ows/1.1"\
  xmlns:gml="http://www.opengis.net/gml"\
  xmlns:ogc="http://www.opengis.net/ogc"\
  xmlns:wcs="http://www.opengis.net/wcs/1.1.1"\
  xmlns:xlink="http://www.w3.org/1999/xlink"\
  xsi:schemaLocation="http://www.opengis.net/wps/1.0.0\ http://schemas.opengis.net/wps/1.0.0/wpsAll.xsd">\
  <ows:Identifier>simulator</ows:Identifier>\
      <wps:DataInputs>\
          <wps:Input>\
              <ows:Identifier>data</ows:Identifier>\
              <wps:Data>\
                  <wps:ComplexData mimeType="application/json">\
                    <![CDATA['+ jsonData + ']]>\
                  </wps:ComplexData>\
              </wps:Data>\
          </wps:Input>\
      </wps:DataInputs>\
      <wps:ResponseForm>\
          <wps:RawDataOutput mimeType="application/json">\
              <ows:Identifier>response</ows:Identifier>\
          </wps:RawDataOutput>\
      </wps:ResponseForm>\
  </wps:Execute>';
  var requestOptions = {
    method: 'POST',
    headers: myHeaders,
    body: raw
  };

  fetch(GEOSERVER_URL + "/wps", requestOptions)
    .then(response => response.json())
    .then(result => {
      updateMap(result, map)
      document.getElementById('submitWaitMessage').style.display = "none"
    })
    .catch(error => {
      document.getElementById('submitWaitMessage').style.display = "none"
      document.getElementById('submitErrorMessage').style.display = "inline-block"
    });
};

document.getElementById('submitButton').addEventListener('click', function (e) {
  e.preventDefault();
  let criteria = []
  document.getElementById('submitWaitMessage').style.display = "inline-block"
  document.getElementById('submitErrorMessage').style.display = "none"
  // Escolas 
  let criterium = {
    FunctionType: parseInt(document.getElementById('schoolDistance').value),
    Weight: parseInt(document.getElementById('schoolWeightRange').value)
  }
  criteria.push(criterium)
  // Estações de metro
  criterium = {
    FunctionType: parseInt(document.getElementById('metroDistance').value),
    Weight: parseInt(document.getElementById('metroWeightRange').value)
  }
  criteria.push(criterium)
  // Estradas
  criterium = {
    FunctionType: parseInt(document.getElementById('roadDistance').value),
    Weight: parseInt(document.getElementById('roadWeightRange').value)
  }
  criteria.push(criterium)
  // Identificação da pessoa
  let payload = {
    PersonId: document.getElementById('idNumber').value,
    Criteria: criteria
  };
  wpsRequest(JSON.stringify(payload), map);
});

async function reverseGeocode(coords) {
  var response = await fetch('http://nominatim.openstreetmap.org/reverse?format=json&lon=' + coords[0] + '&lat=' + coords[1]);
  var json = await response.json();
  return json.display_name;
}