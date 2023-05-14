<?xml version="1.0" encoding="UTF-8"?>
<StyledLayerDescriptor xmlns="http://www.opengis.net/sld" xmlns:gml="http://www.opengis.net/gml" version="1.0.0" xmlns:sld="http://www.opengis.net/sld" xmlns:ogc="http://www.opengis.net/ogc">
  <UserLayer>
    <sld:LayerFeatureConstraints>
      <sld:FeatureTypeConstraint/>
    </sld:LayerFeatureConstraints>
    <sld:UserStyle>
      <sld:Name>SuitabilityStyle</sld:Name>
      <sld:FeatureTypeStyle>
        <sld:Rule>
          <sld:RasterSymbolizer>
            <sld:ChannelSelection>
              <sld:GrayChannel>
                <sld:SourceChannelName>1</sld:SourceChannelName>
              </sld:GrayChannel>
            </sld:ChannelSelection>
            <sld:ColorMap type="ramp">
              <sld:ColorMapEntry color="#d7191c" label="1" quantity="1"/>
              <sld:ColorMapEntry color="#df382b" label="2" quantity="2"/>
              <sld:ColorMapEntry color="#e75839" label="3" quantity="3"/>
              <sld:ColorMapEntry color="#ef7748" label="4" quantity="4"/>
              <sld:ColorMapEntry color="#f79656" label="5" quantity="5"/>
              <sld:ColorMapEntry color="#fdb266" label="6" quantity="6"/>
              <sld:ColorMapEntry color="#fec37a" label="7" quantity="7"/>
              <sld:ColorMapEntry color="#fed48e" label="8" quantity="8"/>
              <sld:ColorMapEntry color="#fee5a2" label="9" quantity="9"/>
              <sld:ColorMapEntry color="#fff6b6" label="10" quantity="10"/>
              <sld:ColorMapEntry color="#f6fbb7" label="11" quantity="11"/>
              <sld:ColorMapEntry color="#e3f3a5" label="12" quantity="12"/>
              <sld:ColorMapEntry color="#d0eb93" label="13" quantity="13"/>
              <sld:ColorMapEntry color="#bde381" label="14" quantity="14"/>
              <sld:ColorMapEntry color="#abdb6f" label="15" quantity="15"/>
              <sld:ColorMapEntry color="#90ce64" label="16" quantity="16"/>
              <sld:ColorMapEntry color="#72c05b" label="17" quantity="17"/>
              <sld:ColorMapEntry color="#55b252" label="18" quantity="18"/>
              <sld:ColorMapEntry color="#37a44a" label="19" quantity="19"/>
              <sld:ColorMapEntry color="#1a9641" label="20" quantity="20"/>
            </sld:ColorMap>
          </sld:RasterSymbolizer>
        </sld:Rule>
      </sld:FeatureTypeStyle>
    </sld:UserStyle>
  </UserLayer>
</StyledLayerDescriptor>
