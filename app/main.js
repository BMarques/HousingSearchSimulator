import './style.css';
import { Map, View } from 'ol';
import TileLayer from 'ol/layer/Tile';
import TileWMS from 'ol/source/TileWMS';
import ImageWMS from 'ol/source/ImageWMS';
import OSM from 'ol/source/OSM';
import * as olProj from 'ol/proj';
import ImageLayer from 'ol/layer/Image';

const map = new Map({
  target: 'map',
  layers: [
    new TileLayer({
      source: new OSM() // Basemap using OpenStreetMap
    })
  ],
  view: new View({
    center: [0, 0],
    center: olProj.transform([-9.15, 38.75], 'EPSG:4326', 'EPSG:3857'),
    zoom: 12.5
  })
});

map.removeLayer()

function updateMap(wmsInfo, map) {
  // Enable CORS on GeoServer first!
  // https://docs.geoserver.org/latest/en/user/production/container.html#enable-cors
  // let suitabilityLayer = new TileLayer({
  //   source: new TileWMS({
  //     url: wmsInfo.url,
  //     params: {
  //       'LAYERS': wmsInfo.layer
  //     },
  //     serverType: 'geoserver',
  //     crossOrigin: 'anonymous',
  //     hidpi: true
  //   })
  // })
  let suitabilityLayer = new ImageLayer({
    source: new ImageWMS({
      url: wmsInfo.url,
      params: {'LAYERS': wmsInfo.layer},
      ratio: 1,
      serverType: 'geoserver',
      crossOrigin: 'anonymous'
    })
  })

  map.addLayer(suitabilityLayer);
  map.render();
}

function wpsRequest (jsonData, map) {
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
                  <wps:LiteralData>' +
                    jsonData +
                  '</wps:LiteralData>\
              </wps:Data>\
          </wps:Input>\
      </wps:DataInputs>\
      <wps:ResponseForm>\
          <wps:RawDataOutput>\
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
      })
    .catch(error => console.log('error', error));
};

document.getElementById('submitButton').addEventListener('click', function (e) {
  e.preventDefault();
  
  let criteria = []

  // Escolas 
  let criterium = {
    CriteriaType: 1,
    FunctionType: parseInt(document.getElementById('schoolDistance').value),
    Weight: parseInt(document.getElementById('schoolWeightRange').value)
  }
  criteria.push(criterium)

  // Estações de metro
  criterium = {
    CriteriaType: 2,
    FunctionType: parseInt(document.getElementById('metroDistance').value),
    Weight: parseInt(document.getElementById('metroWeightRange').value)
  }
  criteria.push(criterium)

  let payload = {
    PersonId: document.getElementById('idNumber').value,
    Criteria: criteria
  };

  wpsRequest(JSON.stringify(payload), map);
  
});