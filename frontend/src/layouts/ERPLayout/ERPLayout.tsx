import { useEffect, useState } from "react";
import { Outlet, useLocation } from "react-router-dom";
import { BottomNav } from "./BottomNav";
import styles from "./ERPLayout.module.css";
import { MasterMenu } from "./MasterMenu";
import { ProcurementMenu } from "./ProcurementMenu";
import { ProductionMenu } from "./ProductionMenu";
import { SalesMenu } from "./SalesMenu";
import { TopBar } from "./TopBar";

export function ERPLayout() {
  const location = useLocation();
  const [procurementOpen, setProcurementOpen] = useState(false);
  const [productionOpen, setProductionOpen] = useState(false);
  const [salesOpen, setSalesOpen] = useState(false);
  const [masterOpen, setMasterOpen] = useState(false);
  const [moreOpen, setMoreOpen] = useState(false);

  useEffect(() => {
    setProcurementOpen(false);
    setProductionOpen(false);
    setSalesOpen(false);
    setMasterOpen(false);
    setMoreOpen(false);
  }, [location.pathname]);

  useEffect(() => {
    function onKeyDown(event: KeyboardEvent) {
      if (event.key === "Escape") {
        setProcurementOpen(false);
        setProductionOpen(false);
        setSalesOpen(false);
        setMasterOpen(false);
        setMoreOpen(false);
      }
    }

    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, []);

  return (
    <div className={styles.shell}>
      <TopBar />
      <main className={styles.main}>
        <Outlet />
      </main>
      {procurementOpen ? (
        <>
          <button
            type="button"
            className={styles.backdrop}
            aria-label="Close procurement menu"
            onClick={() => setProcurementOpen(false)}
          />
          <ProcurementMenu onClose={() => setProcurementOpen(false)} />
        </>
      ) : null}
      {productionOpen ? (
        <>
          <button
            type="button"
            className={styles.backdrop}
            aria-label="Close production menu"
            onClick={() => setProductionOpen(false)}
          />
          <ProductionMenu onClose={() => setProductionOpen(false)} />
        </>
      ) : null}
      {salesOpen ? (
        <>
          <button
            type="button"
            className={styles.backdrop}
            aria-label="Close sales menu"
            onClick={() => setSalesOpen(false)}
          />
          <SalesMenu onClose={() => setSalesOpen(false)} />
        </>
      ) : null}
      {masterOpen ? (
        <>
          <button
            type="button"
            className={styles.backdrop}
            aria-label="Close master menu"
            onClick={() => setMasterOpen(false)}
          />
          <MasterMenu onClose={() => setMasterOpen(false)} />
        </>
      ) : null}
      <BottomNav
        procurementOpen={procurementOpen}
        productionOpen={productionOpen}
        salesOpen={salesOpen}
        masterOpen={masterOpen}
        moreOpen={moreOpen}
        onToggleProcurement={() => {
          setMoreOpen(false);
          setProductionOpen(false);
          setSalesOpen(false);
          setMasterOpen(false);
          setProcurementOpen((open) => !open);
        }}
        onToggleProduction={() => {
          setMoreOpen(false);
          setProcurementOpen(false);
          setSalesOpen(false);
          setMasterOpen(false);
          setProductionOpen((open) => !open);
        }}
        onToggleSales={() => {
          setMoreOpen(false);
          setProcurementOpen(false);
          setProductionOpen(false);
          setMasterOpen(false);
          setSalesOpen((open) => !open);
        }}
        onToggleMaster={() => {
          setMoreOpen(false);
          setProcurementOpen(false);
          setProductionOpen(false);
          setSalesOpen(false);
          setMasterOpen((open) => !open);
        }}
        onToggleMore={() => {
          setProcurementOpen(false);
          setProductionOpen(false);
          setSalesOpen(false);
          setMasterOpen(false);
          setMoreOpen((open) => !open);
        }}
        onNavigate={() => {
          setProcurementOpen(false);
          setProductionOpen(false);
          setSalesOpen(false);
          setMasterOpen(false);
          setMoreOpen(false);
        }}
      />
    </div>
  );
}
