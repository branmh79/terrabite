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
import { IonImageryProvider } from "cesium";

const degToRad = (deg) => deg * Math.PI / 180;

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
const [progress, setProgress] = useState({ completed: 0, total: 1 });
const [progressText, setProgressText] = useState("Initializing...");
const [showWelcome, setShowWelcome] = useState(false);

useEffect(() => {
  const visited = localStorage.getItem("visited");
  if (!visited) {
    setShowWelcome(true);
    localStorage.setItem("visited", "true");
  }
}, []);


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
    // Send prediction request
    const res = await fetch("https://terrabite.onrender.com/predict", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(region),
    });

    const data = await res.json();
    const sessionId = data.session_id;
    setProgress({ completed: 0, total: 1 });
    setProgressText("Initializing...");

    // Start polling
    const pollProgress = async () => {
      try {
        const res = await fetch(`https://terrabite.onrender.com/progress/${sessionId}`);
        const prog = await res.json();

        setProgress(prog);
        setProgressText(`Analyzing satellite tiles: ${prog.completed} of ${prog.total} complete`);


        if (prog.completed < prog.total) {
          setTimeout(pollProgress, 1000);
        } else {
          try {
            const tilesRes = await fetch(`https://terrabite.onrender.com/results/${sessionId}`);
            const tilesJson = await tilesRes.json();
            setHeatmapTiles(tilesJson.tiles);
          } catch (err) {
            console.error("❌ Failed to fetch tiles:", err);
          }
        }
      } catch (err) {
        console.error("Progress polling error:", err);
      }
    };

    pollProgress();

  } catch (err) {
    console.error("❌ Prediction error:", err);
  }
};


  useEffect(() => {
    if (!viewerRef.current) return;
    window.CESIUM_BASE_URL = '/Cesium/';

    const viewerInstance = new Viewer(viewerRef.current, {
      baseLayerPicker: false,
      animation: false,
      timeline: false,
      infoBox: true,           // ✅ enable the info box
      selectionIndicator: true // ✅ show selected entity box
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
    if (!viewer || !viewer.scene || !viewer.scene.canvas || !Array.isArray(heatmapTiles)) return;


  // Optional: Clear previous heatmap tiles
  const heatmapEntities = [];

    heatmapTiles.forEach((tile) => {
      const { lat, lon, score, id, tile_width_deg } = tile;
      const clampedScore = Math.min(1, Math.max(0, parseFloat(score)));
      if (isNaN(clampedScore)) return;
      const degreesPerTile = 0.0088; // ~1km tile width at equator





    const clampLat = (val) => Math.max(-89.9, Math.min(89.9, val));
    const clampLon = (val) => (((val + 180) % 360 + 360) % 360) - 180;

    const rectangle = Rectangle.fromDegrees(
      clampLon(lon - degreesPerTile / 2),
      clampLat(lat - degreesPerTile / 2),
      clampLon(lon + degreesPerTile / 2),
      clampLat(lat + degreesPerTile / 2)
    );



    let color;
    if (clampedScore >= 0.9) color = Color.WHITE.withAlpha(0.5);
    else if (clampedScore >= 0.7) color = Color.YELLOW.withAlpha(0.5);
    else if (clampedScore >= 0.5) color = Color.ORANGE.withAlpha(0.4);
    else if (clampedScore >= 0.3) color = Color.RED.withAlpha(0.4);
    else color = Color.DARKRED.withAlpha(0.5);


    const entity = viewer.entities.add({
      rectangle: {
        coordinates: rectangle,
        material: color,
        outline: false,
        heightReference: HeightReference.CLAMP_TO_GROUND,
      },
      description: `
        <strong>Score:</strong> ${clampedScore.toFixed(3)}<br/>
        <strong>Latitude:</strong> ${lat.toFixed(5)}<br/>
        <strong>Longitude:</strong> ${lon.toFixed(5)}<br/><br/>
        <img src="https://terrabite.onrender.com/tiles/${id}.png" 
            width="256" 
            height="256" 
            style="border-radius: 6px; box-shadow: 0 0 6px rgba(0,0,0,0.6);" />
      `,

    });

    entity.isHeatmapTile = true;
    heatmapEntities.push(entity);
  });


  return () => {
    heatmapEntities.forEach((entity) => viewer.entities.remove(entity));
  };
}, [viewer, heatmapTiles]);


useEffect(() => {
  if (!viewer) return;

  let previousHovered = null;

  const handler = new ScreenSpaceEventHandler(viewer.scene.canvas);

  handler.setInputAction((movement) => {
    const picked = viewer.scene.pick(movement.endPosition);
    const entity = picked?.id;

    // Restore previously hovered tile if different or if cursor left
    if (previousHovered && previousHovered !== entity) {
      if (previousHovered.rectangle && previousHovered.isHeatmapTile) {
        previousHovered.rectangle.extrudedHeight = undefined;
      }
      previousHovered = null;
    }

    // Apply lift only to valid heatmap tile
    if (entity && entity.rectangle && entity.isHeatmapTile) {
      if (entity !== previousHovered) {
        entity.rectangle.extrudedHeight = 100;
        previousHovered = entity;
      }
    }
  }, ScreenSpaceEventType.MOUSE_MOVE);

  return () => handler.destroy();
}, [viewer]);



  useEffect(() => {
    if (!viewer) return;

    const addBaseImagery = async () => {
      const imageryLayer = await IonImageryProvider.fromAssetId(3); // Bing Aerial with Labels
      viewer.imageryLayers.addImageryProvider(imageryLayer);
    };

    addBaseImagery();

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
      const clampLat = (val) => Math.max(-89.9, Math.min(89.9, val));
      const clampLon = (val) => (((val + 180) % 360 + 360) % 360) - 180;

      const minLat = clampLat(lat - 0.05);
      const maxLat = clampLat(lat + 0.05);
      const minLon = clampLon(lon - 0.05);
      const maxLon = clampLon(lon + 0.05);
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
      coordinates: Rectangle.fromDegrees(minLon, minLat, maxLon, maxLat),
      material: Color.fromCssColorString("#00cccc").withAlpha(0.4),

      outline: true,
      outlineColor: Color.CYAN,
      heightReference: HeightReference.CLAMP_TO_GROUND,
    }),


    });
  }, [viewer, centerCartographic, radiusKm]);

  useEffect(() => {
    const style = document.createElement("style");
    style.innerHTML = `
      .cesium-infoBox {
        margin-top: 40px !important;
      }
    `;
    document.head.appendChild(style);
    return () => {
      document.head.removeChild(style);
    };
  }, []);

  return (
    <div style={{ position: "relative", height: "100vh", width: "100%" }}>
{showWelcome && (
  <>
    {/* Dimmed overlay */}
    <div style={{
      position: "fixed",
      top: 0,
      left: 0,
      width: "100vw",
      height: "100vh",
      backgroundColor: "rgba(0, 0, 0, 0.7)",
      zIndex: 9998
    }} />

    {/* Welcome modal */}
    <div style={{
      position: "absolute",
      top: "8%",
      left: "50%",
      transform: "translateX(-50%)",
      backgroundColor: "#111",
      color: "#0ff",
      padding: "24px",
      borderRadius: "12px",
      zIndex: 9999,
      width: "440px",
      fontFamily: "monospace",
      boxShadow: "0 4px 20px rgba(0,0,0,0.5)"
    }}>
      <h3 style={{ marginTop: 0 }}>👋 Welcome to TerraBite</h3>
      <p style={{ marginBottom: "8px" }}>
        The U.S. Census defines a <strong>food desert</strong> as an area that:
      </p>
      <ul style={{ paddingLeft: "20px", marginBottom: "12px" }}>
        <li>Has a poverty rate ≥ 20%</li>
        <li>AND is ≥ 1 mile from a supermarket (urban) or ≥ 10 miles (rural)</li>
      </ul>
      <p style={{ marginBottom: "12px" }}>
        This tool uses satellite imagery and AI to detect visual patterns linked to these conditions.
      </p>
      <p style={{ marginBottom: "12px" }}>
        ➤ Use the 📍 pin tool to select a region.<br />
        ➤ Adjust the side length and click <strong>Confirm</strong>.<br />
        ➤ View colored tiles ranked by their food desert likelihood.
      </p>
      <p style={{ marginBottom: "18px" }}>
        <strong>Tile Score Legend:</strong><br />
        <span style={{ color: "#ff5555" }}>0.0</span> = unlikely to be a food desert<br />
        <span style={{ color: "#00ffff" }}>1.0</span> = highly likely
      </p>

      {/* Centered button */}
      <div style={{ textAlign: "center" }}>
        <button
          onClick={() => setShowWelcome(false)}
          style={{
            backgroundColor: "#0ff",
            color: "#000",
            border: "none",
            padding: "8px 18px",
            borderRadius: "6px",
            cursor: "pointer",
            fontWeight: "bold"
          }}
        >
          Let’s go!
        </button>
      </div>
    </div>
  </>
)}



      {/* Selection Tool Icon with Tooltip */}
<div style={{ position: "absolute", top: 45, right: 7.5, zIndex: 10 }}>
  <div
    onClick={() => {
      setSelectMode((prev) => !prev);
      setCenterCartographic(null);
      setSelectionPlaced(false);
    }}
    style={{
      width: 32,
      height: 32,
      backgroundColor: selectMode ? "#8fd4dd" : "#2c2c2c", // dark default background
      border: "1px solid #444", // matches Cesium tool buttons
      borderRadius: 3,
      cursor: "pointer",
      display: "flex",
      alignItems: "center",
      justifyContent: "center",
      fontSize: 18,
      position: "relative",
      boxShadow: "0 1px 3px rgba(0, 0, 0, 0.3)", // subtle elevation
    }}

    onMouseEnter={() => {
      const tooltip = document.getElementById("toolTip");
      if (tooltip) tooltip.style.display = "block";
    }}
    onMouseLeave={() => {
      const tooltip = document.getElementById("toolTip");
      if (tooltip) tooltip.style.display = "none";
    }}
  >
    📍
  </div>
  <div
    id="toolTip"
    style={{
      display: "none",
      position: "absolute",
      top: "40px",
      right: 0,
      backgroundColor: "#222",
      color: "#fff",
      padding: "6px 10px",
      borderRadius: "6px",
      fontFamily: "monospace",
      fontSize: "12px",
      width: "400px",
      boxShadow: "0 2px 6px rgba(0,0,0,0.2)",
    }}
  >
    Click to enter selection mode. Then, click on the globe to define a region. Adjust the size using the slider, and hit "Confirm" to start calculating food desert probability.
  </div>
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
      Side-length: {radiusKm} km
      <input
        type="range"
        min={1}
        max={5}
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
      Preparing satellite imagery and fetching region data...
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
{progress && progress.total > 1 && progress.completed < progress.total && (
  <div
    style={{
      position: "absolute",
      top: 20,
      left: "50%",
      transform: "translateX(-50%)",
      backgroundColor: "#111",
      color: "#0ff",
      padding: "10px 20px",
      borderRadius: "8px",
      fontFamily: "monospace",
      fontSize: "13px",
      zIndex: 999,
      textAlign: "center",
    }}
  >
    <div>{progressText}</div>
    <div
      style={{
        width: "100%",
        height: 10,
        backgroundColor: "#333",
        borderRadius: 4,
        marginTop: 6,
      }}
    >
      <div
        style={{
          width: `${(progress.completed / progress.total) * 100}%`,
          height: "100%",
          backgroundColor: "#0ff",
          borderRadius: 4,
          transition: "width 0.3s ease",
        }}
      />
    </div>
  </div>
)}

      <div ref={viewerRef} style={{ height: "100%", width: "100%" }} />
    </div>
  );
}