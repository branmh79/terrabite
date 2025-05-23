import {
  Ion,
  Viewer,
  Cesium3DTileset,
} from "cesium";
import "cesium/Build/Cesium/Widgets/widgets.css";
import { useEffect, useRef, useState } from "react";

// Set your Cesium Ion token
Ion.defaultAccessToken =
  "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJqdGkiOiIxMzEwY2M1ZS03NThmLTQwYmQtOGViZS0wMzlmYjVjYTc0NTUiLCJpZCI6MzA1NDI2LCJpYXQiOjE3NDc5NjkwMzJ9.Z4nYi_tZpHiysag2soHdOMih6nELUaFDJ6BfujbDCwI";

export default function Globe() {
  const viewerRef = useRef(null);
  const [viewer, setViewer] = useState(null);

  useEffect(() => {
    if (!viewerRef.current) return;

    const viewerInstance = new Viewer(viewerRef.current, {
      baseLayerPicker: false,
      animation: false,
      timeline: false,
      imageryProvider: false,
    });

    setViewer(viewerInstance);

    return () => {
      viewerInstance.destroy();
    };
  }, []);

  useEffect(() => {
    const loadTileset = async () => {
    if (!viewer) return;

    const tileset = await Cesium3DTileset.fromIonAssetId(2275207);
    viewer.scene.primitives.add(tileset);
    await viewer.zoomTo(tileset);

    // Render quality improvements
    viewer.scene.globe.maximumScreenSpaceError = 1.0;
    viewer.scene.highDynamicRange = true;
    viewer.resolutionScale = window.devicePixelRatio;
    viewer.scene.fog.enabled = false;
    viewer.scene.skyAtmosphere.brightnessShift = 0.3;
    };


    loadTileset();
  }, [viewer]);

  return <div ref={viewerRef} style={{ height: "100vh", width: "100%" }} />;
}
