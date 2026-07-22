import { Routes, Route, NavLink } from "react-router-dom";
import UploadBill from "./pages/UploadBill.jsx";
import ReviewBill from "./pages/ReviewBill.jsx";
import SearchDashboard from "./pages/SearchDashboard.jsx";
import BillHistory from "./pages/BillHistory.jsx";

export default function App() {
  return (
    <div>
      <nav>
        <NavLink to="/" end>Search</NavLink>
        <NavLink to="/upload">Upload bill</NavLink>
        <NavLink to="/bills">Review queue</NavLink>
      </nav>
      <div className="container">
        <Routes>
          <Route path="/" element={<SearchDashboard />} />
          <Route path="/upload" element={<UploadBill />} />
          <Route path="/bills" element={<BillHistory />} />
          <Route path="/review/:billId" element={<ReviewBill />} />
        </Routes>
      </div>
    </div>
  );
}
