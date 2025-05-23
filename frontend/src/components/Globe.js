import {
  Ion,
  Viewer,
  Cesium3DTileset,
  ScreenSpaceEventHandler,
  ScreenSpaceEventType,
  Cartographic,
  Math as CesiumMath,
  createWorldTerrainAsync,
  Color,
  Rectangle,
  RectangleGraphics,
  HeightReference,
  Cartesian3,
} from "cesium";
import "cesium/Build/Cesium/Widgets/widgets.css";
import { useEffect, useRef, useState } from "react";

Ion.defaultAccessToken =
  "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJqdGkiOiIxMzEwY2M1ZS03NThmLTQwYmQtOGViZS0wMzlmYjVjYTc0NTUiLCJpZCI6MzA1NDI2LCJpYXQiOjE3NDc5NjkwMzJ9.Z4nYi_tZpHiysag2soHdOMih6nELUaFDJ6BfujbDCwI";

export default function Globe() {
  const viewerRef = useRef(null);
  const [viewer, setViewer] = useState(null);
  const [selectMode, setSelectMode] = useState(false);
  const [centerCartographic, setCenterCartographic] = useState(null);
  const [radiusKm, setRadiusKm] = useState(5); // default radius
    const [selectionPlaced, setSelectionPlaced] = useState(false);
const [heatmapTiles, setHeatmapTiles] = useState([]);
const [isLoading, setIsLoading] = useState(false);

const handleRegionConfirm = async () => {
  if (!centerCartographic) return;

  const lat = CesiumMath.toDegrees(centerCartographic.latitude);
  const lon = CesiumMath.toDegrees(centerCartographic.longitude);

  const region = {
    latitude: lat,
    longitude: lon,
    radius_km: radiusKm,
  };

  console.log("Sending to backend:", region);

  try {
    const response = await fetch("https://terrabite.onrender.com/predict", {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(region),
    });

    if (!response.ok) throw new Error("Failed to fetch prediction");

    const text = await response.text();

    if (!response.ok) {
    console.error("❌ Backend error:", text);
    throw new Error("Failed to fetch prediction");
    }

    const data = JSON.parse(text);
    setHeatmapTiles(data.tiles);

    console.log("✅ Prediction Result:", data);
    // You can optionally handle or visualize `data.tiles` here
  } catch (err) {
    console.error("❌ Prediction request failed:", err);
  }
};

  useEffect(() => {
    if (!viewerRef.current) return;
window.CESIUM_BASE_URL = '/Cesium/';

    const viewerInstance = new Viewer(viewerRef.current, {
    baseLayerPicker: false,
    animation: false,
    timeline: false,
    });


    setViewer(viewerInstance);

    viewerInstance.scene.postRender.addEventListener(async function once() {
    viewerInstance.scene.postRender.removeEventListener(once); // run once

    const terrain = await createWorldTerrainAsync();
    viewerInstance.terrainProvider = terrain;
    });


    return () => viewerInstance.destroy();
  }, []);

useEffect(() => {
    if (!viewer || !viewer.scene || !viewer.scene.canvas || heatmapTiles.length === 0) return;


  // Optional: Clear previous heatmap tiles
  const heatmapEntities = [];

    heatmapTiles.forEach(({ lat, lon, score }) => {
    const clampedScore = Math.min(1, Math.max(0, parseFloat(score)));
    if (isNaN(clampedScore)) return;
    const halfSide = 0.01; // ~1km side (adjust as needed)

    const rectangle = Rectangle.fromDegrees(
      lon - halfSide,
      lat - halfSide,
      lon + halfSide,
      lat + halfSide
    );

    let color;
    if (clampedScore >= 0.9) color = Color.WHITE;
    else if (clampedScore >= 0.7) color = Color.YELLOW;
    else if (clampedScore >= 0.5) color = Color.ORANGE;
    else if (clampedScore >= 0.3) color = Color.RED;
    else color = Color.DARKRED.withAlpha(0.9);



    const entity = viewer.entities.add({
      rectangle: {
        coordinates: rectangle,
        material: color,
        outline: false,
        heightReference: HeightReference.CLAMP_TO_GROUND,
      },
    });

    heatmapEntities.push(entity);
  });

  return () => {
    heatmapEntities.forEach((entity) => viewer.entities.remove(entity));
  };
}, [viewer, heatmapTiles]);

  useEffect(() => {
    if (!viewer) return;

    const loadTileset = async () => {
      const tileset = await Cesium3DTileset.fromIonAssetId(2275207);
      viewer.scene.primitives.add(tileset);
      await viewer.zoomTo(tileset);

      viewer.scene.globe.maximumScreenSpaceError = 1.0;
      viewer.scene.highDynamicRange = true;
      viewer.resolutionScale = window.devicePixelRatio;
      viewer.scene.fog.enabled = false;
      viewer.scene.skyAtmosphere.brightnessShift = 0.3;
    };

    loadTileset();
  }, [viewer]);

    useEffect(() => {
    if (!viewer) return;

    viewer.scene.screenSpaceCameraController.enableRotate = true;
    viewer.canvas.style.cursor = selectMode ? "crosshair" : "default";

    const handler = new ScreenSpaceEventHandler(viewer.scene.canvas);

    handler.setInputAction((click) => {
        if (!selectMode) return;

        const ray = viewer.camera.getPickRay(click.position);
        const cartesian = viewer.scene.globe.pick(ray, viewer.scene);
        if (!cartesian) return;

        const cartographic = Cartographic.fromCartesian(cartesian);
        setCenterCartographic(cartographic);
        setSelectionPlaced(true);

    }, ScreenSpaceEventType.LEFT_CLICK);

    return () => {
        handler.destroy();
        viewer.canvas.style.cursor = "default";
    };
    }, [viewer, selectMode]);

  // Remove previous marker each update
  useEffect(() => {
    if (!viewer || !centerCartographic) return;

    viewer.entities.removeAll();

    const lat = CesiumMath.toDegrees(centerCartographic.latitude);
    const lon = CesiumMath.toDegrees(centerCartographic.longitude);

    const center = Cartesian3.fromRadians(
      centerCartographic.longitude,
      centerCartographic.latitude,
      5
    );

    viewer.entities.add({
    position: center,
    point: {
    pixelSize: 10,
    color: Color.CYAN,
    outlineColor: Color.BLACK,
    outlineWidth: 2,
    disableDepthTestDistance: Number.POSITIVE_INFINITY,
    },

    label: {
    text: `Lat: ${lat.toFixed(4)}°\nLon: ${lon.toFixed(4)}°`,
    font: "14px sans-serif",
    fillColor: Color.CYAN,
    outlineColor: Color.BLACK,
    outlineWidth: 1,
    verticalOrigin: CesiumMath.TOP,
    pixelOffset: new Cartesian3(0, -35, 0),
    disableDepthTestDistance: Number.POSITIVE_INFINITY, // prevents label flickering under terrain
    },


    rectangle: new RectangleGraphics({
    coordinates: Rectangle.fromDegrees(
        lon - radiusKm / 111,
        lat - radiusKm / 111,
        lon + radiusKm / 111,
        lat + radiusKm / 111
    ),
    material: Color.CYAN.withAlpha(0.2),
    outline: true,
    outlineColor: Color.CYAN,
    heightReference: HeightReference.CLAMP_TO_GROUND,
    }),

    });
  }, [viewer, centerCartographic, radiusKm]);

  return (
    <div style={{ position: "relative", height: "100vh", width: "100%" }}>
      {/* Selection Tool Icon */}
        <div
        onClick={() => {
            setSelectMode((prev) => !prev);
            setCenterCartographic(null);
            setSelectionPlaced(false);
        }}


        title="Click to enter selection mode. Then click anywhere on the globe to place a square region. Adjust with the slider, then confirm."

        style={{
          position: "absolute",
          top: 45, // 👈 appears below Cesium buttons
          right: 7.5,
          zIndex: 10,
          width: 30,
          height: 30,
          backgroundColor: selectMode ? "#0ff" : "#fff",
          border: "1px solid #ccc",
          borderRadius: 4,
          cursor: "pointer",
          display: "flex",
          alignItems: "center",
          justifyContent: "center",
          fontSize: 18,
        }}
      >
        📍
      </div>

      {(selectMode || selectionPlaced) && centerCartographic && (
  <div
    style={{
      position: "absolute",
      top: 100,
      right: 10,
      zIndex: 10,
      backgroundColor: "#222",
      color: "#0ff",
      padding: "10px",
      borderRadius: "8px",
      fontFamily: "monospace",
      display: "flex",
      flexDirection: "column",
      gap: "8px",
    }}
  >
    <div>
      Radius: {radiusKm} km
      <input
        type="range"
        min={1}
        max={20}
        value={radiusKm}
        onChange={(e) => setRadiusKm(parseInt(e.target.value))}
        style={{ width: "120px", marginLeft: "10px" }}
      />
    </div>
    <button
    onClick={async () => {
    setIsLoading(true); // 👈 Show loading message
    setSelectionPlaced(false);
    setSelectMode(false);
    setCenterCartographic(null); // 👈 Clear selection
    
    if (viewer) viewer.entities.removeAll(); // 👈 Remove circle/label/box

    try {
        await handleRegionConfirm();
    } catch (err) {
        console.error("❌ Prediction error:", err);
    } finally {
        setIsLoading(false); // 👈 Hide loading message
    }
    }}


      style={{
        backgroundColor: "#0ff",
        color: "#000",
        border: "none",
        borderRadius: "4px",
        padding: "4px 8px",
        cursor: "pointer",
        fontFamily: "monospace",
        fontSize: "13px",
      }}
    >
      Confirm
    </button>
  </div>
)}

{isLoading && (
  <div
    style={{
      position: "absolute",
      top: 20,
      left: "50%",
      transform: "translateX(-50%)",
      backgroundColor: "#000",
      color: "#0ff",
      padding: "10px 20px",
      borderRadius: "8px",
      fontFamily: "monospace",
      fontSize: "14px",
      zIndex: 999,
    }}
  >
    Calculating food desert levels...
  </div>
)}

<div
  style={{
    position: "absolute",
    bottom: 20,
    left: 20,
    zIndex: 999,
    backgroundColor: "#000",
    padding: "10px",
    borderRadius: "6px",
    fontFamily: "monospace",
    color: "#fff",
    fontSize: "12px",
  }}
>
  <div style={{ marginBottom: 5 }}>Food Desert Score</div>
  <div
    style={{
      width: 160,
      height: 12,
      background: "linear-gradient(to right, #8B0000, red, orange, yellow, white)",
      borderRadius: "4px",
    }}
  />
  <div style={{ display: "flex", justifyContent: "space-between" }}>
    <span>0</span>
    <span>0.5</span>
    <span>1</span>
  </div>
</div>

      <div ref={viewerRef} style={{ height: "100%", width: "100%" }} />
    </div>
  );
}
