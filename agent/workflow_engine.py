import re
import json
import os
from datetime import datetime
from typing import Dict, List, Any, Optional
from agent.gemini_agent import GeminiAIAgent, get_gemini_api_key

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA_DIR = os.path.join(BASE_DIR, "data")
PRODUCTS_FILE = os.path.join(DATA_DIR, "products.json")
POLICIES_FILE = os.path.join(DATA_DIR, "policies.json")
SALES_FILE = os.path.join(DATA_DIR, "sales_team.json")
PIPELINE_FILE = os.path.join(DATA_DIR, "pipeline_db.json")

def load_json(filepath: str, default_val=None):
    if not os.path.exists(filepath):
        return default_val if default_val is not None else {}
    with open(filepath, "r", encoding="utf-8") as f:
        return json.load(f)

def save_json(filepath: str, data: Any):
    with open(filepath, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

class MinhAnWorkflowEngine:
    def __init__(self):
        self.products = load_json(PRODUCTS_FILE, [])
        self.policies = load_json(POLICIES_FILE, {})
        self.sales_team = load_json(SALES_FILE, [])
        self.gemini = None
        if get_gemini_api_key():
            try:
                self.gemini = GeminiAIAgent()
            except Exception:
                self.gemini = None

    def reload_data(self):
        self.products = load_json(PRODUCTS_FILE, [])
        self.policies = load_json(POLICIES_FILE, {})
        self.sales_team = load_json(SALES_FILE, [])

    # =========================================================================
    # BƯỚC 1 & 2: TIẾP NHẬN, PHÂN LOẠI & TRÍCH XUẤT THÔNG TIN
    # =========================================================================
    def extract_and_classify(self, raw_text: str) -> Dict[str, Any]:
        """
        Phân tích văn bản yêu cầu từ email hoặc biểu mẫu web.
        Tự động ưu tiên sử dụng Gemini 2.5 Flash để bóc tách thông minh,
        kèm Fallback quy tắc nếu mất kết nối mạng.
        """
        # Thử nghiệm với Gemini LLM trước nếu có API key
        if self.gemini:
            try:
                catalog_summary = "\n".join([
                    f"- {p['sku']}: {p['name']} (Giá: {p['current_price']:,.0f} VND, Tồn: {p['available_stock']})"
                    for p in self.products
                ])
                llm_res = self.gemini.extract_request_with_llm(raw_text, catalog_summary)
                
                # Chuyển đổi định dạng sang schema chuẩn
                raw_items = []
                for it in llm_res.get("items", []):
                    qty = it.get("quantity", 1)
                    if qty is None or qty <= 0:
                        qty = 1
                    raw_items.append({
                        "raw_name": it.get("raw_name") or "",
                        "matched_sku": it.get("matched_sku"),
                        "quantity": qty
                    })

                missing = []
                email = llm_res.get("email")
                phone = llm_res.get("phone")
                if not email and not phone:
                    missing.append("Thông tin liên lạc phản hồi (Email hoặc Số điện thoại người nhận)")
                if not raw_items:
                    missing.append("Danh sách cụ thể chủng loại thiết bị hoặc dịch vụ công nghệ cần báo giá")

                extracted_llm = {
                    "customer_name": llm_res.get("customer_name") or "Quý Khách hàng",
                    "company_name": llm_res.get("company_name") or "Doanh nghiệp (Chưa xác định)",
                    "email": email,
                    "phone": phone,
                    "requested_deadline": llm_res.get("requested_deadline"),
                    "budget": llm_res.get("budget"),
                    "requested_discount_pct": float(llm_res.get("requested_discount_pct") or 0.0),
                    "raw_items": raw_items,
                    "missing_fields": missing,
                    "is_complete": len(missing) == 0,
                    "ai_engine": "Gemini 2.5 Flash"
                }
                return extracted_llm
            except Exception as e:
                # Fallback to local rule engine
                pass

        # ENGINE NỘI BỘ (RULE & REGEX FALLBACK)
        text_lower = raw_text.lower()
        extracted: Dict[str, Any] = {
            "customer_name": None,
            "company_name": None,
            "email": None,
            "phone": None,
            "requested_deadline": None,
            "budget": None,
            "requested_discount_pct": 0.0,
            "raw_items": [],
            "missing_fields": [],
            "is_complete": False
        }

        # 1. Trích xuất Email & SĐT
        email_match = re.search(r'[\w\.-]+@[\w\.-]+\.\w+', raw_text)
        if email_match:
            extracted["email"] = email_match.group(0).strip()

        phone_match = re.search(r'(\+?84|0)(3[2-9]|5[6|8|9]|7[0|6-9]|8[1-5]|9[0-9])[0-9\.\s]{7,10}', raw_text)
        if phone_match:
            extracted["phone"] = phone_match.group(0).strip()

        # 2. Trích xuất Tên người gửi & Tên công ty
        cust_match = re.search(r'(?:tôi là|anh|chị|ông|bà|tên tôi là|từ)\s+([A-ZÀ-Ỹ][a-zà-ỹ]+(?:\s+[A-ZÀ-Ỹ][a-zà-ỹ]+){1,3})', raw_text)
        if cust_match:
            extracted["customer_name"] = cust_match.group(1).strip()
        else:
            first_line = raw_text.strip().splitlines()[0] if raw_text.strip() else ""
            if "kính gửi" in first_line.lower() or "chào" in first_line.lower():
                extracted["customer_name"] = "Quý Khách hàng"
            else:
                extracted["customer_name"] = "Đại diện Quý Doanh Nghiệp"

        comp_match = re.search(r'(?:công ty|cty|doanh nghiệp|tập đoàn)\s+([^,\.\n\r]+)', raw_text, re.IGNORECASE)
        if comp_match:
            extracted["company_name"] = ("Công ty " + comp_match.group(1).strip()) if not comp_match.group(1).strip().lower().startswith("công ty") else comp_match.group(1).strip()
        else:
            extracted["company_name"] = "Doanh nghiệp (Chưa xác định)"

        # 3. Trích xuất Deadline / Thời hạn triển khai
        deadline_match = re.search(r'(?:thời hạn|deadline|bàn giao|giao hàng|hoàn thành|cần gấp trong|trong vòng)\s*[:\-]?\s*([^\.\n,]+?(?:ngày|tuần|tháng|\d{1,2}/\d{1,2}))', raw_text, re.IGNORECASE)
        if deadline_match:
            extracted["requested_deadline"] = deadline_match.group(1).strip()
        elif "trong tuần này" in text_lower or "giao ngay" in text_lower or "cần gấp" in text_lower:
            extracted["requested_deadline"] = "Cần gấp (1-3 ngày)"

        # 4. Trích xuất Ngân sách
        budget_match = re.search(r'(?:ngân sách|budget|tối đa|dự kiến chi)\s*[:\-]?\s*([0-9\.,]+)\s*(triệu|tỷ|tr|vnd|đ|dong)?', raw_text, re.IGNORECASE)
        if budget_match:
            raw_num_str = budget_match.group(1).replace(".", "").replace(",", "")
            try:
                val = float(raw_num_str)
                unit = budget_match.group(2)
                if unit:
                    unit = unit.lower()
                    if "triệu" in unit or "tr" in unit:
                        val *= 1_000_000
                    elif "tỷ" in unit:
                        val *= 1_000_000_000
                elif val < 10000:
                    val *= 1_000_000  # Khách hay ghi "ngân sách 150 triệu" -> 150
                extracted["budget"] = val
            except ValueError:
                pass

        # 5. Trích xuất Yêu cầu chiết khấu
        discount_match = re.search(r'(?:chiết khấu|giảm giá|discount)\s*(?:cho chúng tôi|được không|khoảng|mức)?\s*[:\-]?\s*([0-9]+(?:\.[0-9]+)?)\s*%', raw_text, re.IGNORECASE)
        if discount_match:
            try:
                extracted["requested_discount_pct"] = float(discount_match.group(1))
            except ValueError:
                extracted["requested_discount_pct"] = 0.0

        # 6. Trích xuất Sản phẩm & Số lượng (Phân tích theo từng dòng để tránh bắt nhầm số dòng trên)
        found_items = []
        lines = [line.strip() for line in raw_text.splitlines() if line.strip()]

        for p in self.products:
            # Kiểm tra các aliases
            matched_alias = None
            matched_line = None
            matched_qty = None

            for alias in p["aliases"]:
                for line in lines:
                    line_lower = line.lower()
                    if alias in line_lower:
                        matched_alias = alias
                        matched_line = line_lower
                        
                        # Tìm số lượng trên chính dòng này
                        # Mẫu 1: "5 laptop dell", "1 máy chủ", "5 chiếc laptop"
                        m1 = re.search(rf'(?:^|[\s\-\*•\+])(\d+)\s*(?:chiếc|cái|bộ|gói|thiết bị)?\s*(?:[^,\.]*?){re.escape(alias)}', line_lower)
                        # Mẫu 2: "laptop dell : 5 chiếc", "switch cisco sl: 2"
                        m2 = re.search(rf'{re.escape(alias)}\s*(?:[^,\.]*?)(?:số lượng|qty|sl)?\s*[:\-]?\s*(\d+)', line_lower)
                        
                        if m1:
                            matched_qty = int(m1.group(1))
                        elif m2:
                            matched_qty = int(m2.group(1))
                        else:
                            matched_qty = 1
                        break
                if matched_alias:
                    break

            if matched_alias and matched_qty is not None:
                # Đảm bảo số lượng hợp lý (không bắt nhầm mã số như 5520, 9200, 750)
                if matched_qty > 500 and matched_qty in [5520, 9200, 750, 380, 505, 60]:
                    matched_qty = 1
                found_items.append({
                    "raw_name": p["name"],
                    "matched_sku": p["sku"],
                    "quantity": matched_qty
                })

        # Nếu không match alias nhưng có dòng dạng "- sản phẩm ..."
        if not found_items:
            bullet_matches = re.findall(r'[\-\*•\+]\s*(.+)', raw_text)
            for b in bullet_matches:
                b_clean = b.strip()
                if len(b_clean) > 3:
                    found_items.append({
                        "raw_name": b_clean,
                        "matched_sku": None,
                        "quantity": 1
                    })

        extracted["raw_items"] = found_items

        # 7. KIỂM TRA ĐẦY ĐỦ THÔNG TIN (ĐIỀU KIỆN RẼ NHÁNH SƠ ĐỒ)
        missing = []
        if not extracted["email"] and not extracted["phone"]:
            missing.append("Thông tin liên lạc phản hồi (Email hoặc Số điện thoại người nhận)")
        if not extracted["raw_items"]:
            missing.append("Danh sách cụ thể chủng loại thiết bị hoặc dịch vụ công nghệ cần báo giá")
        else:
            for idx, it in enumerate(extracted["raw_items"], 1):
                if it["quantity"] <= 0:
                    missing.append(f"Số lượng cần cung cấp cho hạng mục '{it['raw_name']}'")
        
        extracted["missing_fields"] = missing
        extracted["is_complete"] = len(missing) == 0

        return extracted

    # =========================================================================
    # BƯỚC 3: NHÁNH "KHÔNG" -> SOẠN EMAIL YÊU CẦU KH LÀM RÕ / BỔ SUNG
    # =========================================================================
    def generate_clarification_request(self, extracted: Dict[str, Any]) -> Dict[str, Any]:
        """Tạo bản nháp email gửi lại khách hàng để làm rõ/bổ sung thông tin."""
        customer = extracted.get("customer_name") or "Quý Khách hàng"
        company = extracted.get("company_name") or "Quý Doanh nghiệp"
        missing = extracted.get("missing_fields", [])

        bullets = "\n".join([f"  • {item}" for item in missing])

        email_body = (
            f"Kính gửi {customer} - {company},\n\n"
            f"Bộ phận Kinh doanh Công ty Cổ phần Thiết bị & Dịch vụ Công nghệ Minh An xin chân thành cảm ơn "
            f"Quý công ty đã tin tưởng gửi yêu cầu báo giá giải pháp công nghệ.\n\n"
            f"Sau khi tiếp nhận và phân loại thông tin sơ bộ, để đội ngũ Kỹ thuật và Kinh doanh của Minh An "
            f"có thể thẩm định tồn kho khả dụng, tính toán khung chiết khấu tối ưu và lên tiến độ triển khai chính xác nhất, "
            f"chúng tôi kính mong Quý khách vui lòng làm rõ/bổ sung một số thông tin còn thiếu sau:\n\n"
            f"{bullets}\n\n"
            f"Quý khách có thể phản hồi trực tiếp qua email này hoặc liên hệ Hotline: 1900 8866 để được chuyên viên phụ trách hỗ trợ ngay.\n\n"
            f"Rất mong sớm nhận được thông tin phản hồi từ Quý công ty để chúng tôi kịp thời hoàn thiện Hồ sơ Báo giá.\n\n"
            f"Trân trọng cảm ơn,\n"
            f"Phòng Kinh doanh Doanh nghiệp B2B\n"
            f"Công ty Thiết bị & Dịch vụ Công nghệ Minh An\n"
            f"Email: b2b-sales@minhan-tech.vn | Website: www.minhan-tech.vn"
        )

        return {
            "status": "CLARIFICATION_REQUIRED",
            "subject": f"[Minh An Tech] Tiếp nhận yêu cầu & Đề nghị làm rõ thông tin báo giá - {company}",
            "body": email_body,
            "missing_fields": missing,
            "next_step": "Chờ khách hàng phản hồi bổ sung -> Quay lại bước Tiếp nhận yêu cầu"
        }

    # =========================================================================
    # BƯỚC 4: NHÁNH "CÓ" -> TẠO HỒ SƠ CƠ HỘI & GẮN NVKD PHỤ TRÁCH
    # =========================================================================
    def assign_sales_rep(self, extracted: Dict[str, Any]) -> Dict[str, Any]:
        """Gán NVKD theo tải công việc tối ưu (người có ít active deals nhất)."""
        # Sắp xếp theo số deals đang mở
        sorted_reps = sorted(self.sales_team, key=lambda x: x.get("active_deals", 0))
        assigned = sorted_reps[0] if sorted_reps else {
            "name": "Trần Thị Bích", "email": "bich.tran@minhan-tech.vn", "phone": "0912.345.602"
        }
        return assigned

    # =========================================================================
    # BƯỚC 5: THẨM ĐỊNH TỒN KHO, GIÁ HIỆN HÀNH & TIẾN ĐỘ VẬN HÀNH
    # =========================================================================
    def verify_inventory_and_pricing(self, items: List[Dict[str, Any]], requested_deadline_str: Optional[str]) -> Dict[str, Any]:
        """
        Đối soát trực tiếp dữ liệu với Kho & Bảng giá hiện hành.
        Khắc phục triệt để lỗi: dùng giá cũ, hứa deadline phi thực tế.
        """
        verified_items = []
        total_list_price = 0.0
        max_delivery_days = 2  # Mặc định giao 2 ngày nếu sẵn kho
        has_stock_shortage = False
        unmatched_items = []

        for raw in items:
            matched_sku = raw.get("matched_sku")
            quantity = raw.get("quantity", 1)

            # Tra cứu từ bảng giá mới nhất
            product = None
            if matched_sku:
                product = next((p for p in self.products if p["sku"] == matched_sku), None)
            else:
                # Thử tìm theo tên
                name_clean = raw.get("raw_name", "").lower()
                for p in self.products:
                    if any(alias in name_clean for alias in p["aliases"]):
                        product = p
                        break

            if product:
                unit_price = product["current_price"]
                available_stock = product["available_stock"]
                restock_lead = product["restock_lead_days"]
                
                line_total = unit_price * quantity
                total_list_price += line_total

                in_stock = available_stock >= quantity
                if in_stock:
                    item_lead_days = 2  # Sẵn sàng xuất kho
                else:
                    item_lead_days = restock_lead + 2  # Cần đặt hàng + kiểm định
                    has_stock_shortage = True

                if item_lead_days > max_delivery_days:
                    max_delivery_days = item_lead_days

                verified_items.append({
                    "sku": product["sku"],
                    "name": product["name"],
                    "unit": product["unit"],
                    "quantity": quantity,
                    "unit_price": unit_price,
                    "line_total": line_total,
                    "available_stock": available_stock,
                    "is_in_stock": in_stock,
                    "missing_quantity": max(0, quantity - available_stock),
                    "lead_time_days": item_lead_days,
                    "stock_status": "Sẵn sàng trong kho" if in_stock else f"Thiếu {quantity - available_stock} {product['unit']} (Chờ nhập {restock_lead} ngày)"
                })
            else:
                unmatched_items.append(raw.get("raw_name"))

        # Phân tích tính khả thi của Deadline khách yêu cầu
        is_deadline_feasible = True
        deadline_warning = None

        if requested_deadline_str:
            # Nhận diện số ngày trong chuỗi deadline
            days_match = re.search(r'(\d+)\s*ngày', requested_deadline_str, re.IGNORECASE)
            if days_match:
                req_days = int(days_match.group(1))
                if req_days < max_delivery_days:
                    is_deadline_feasible = False
                    deadline_warning = (
                        f"Khách hàng yêu cầu giao trong {req_days} ngày, "
                        f"tuy nhiên thời gian cung ứng an toàn tối thiểu là {max_delivery_days} ngày "
                        f"(do có mặt hàng chưa sẵn kho)."
                    )
            elif "cần gấp" in requested_deadline_str.lower() and max_delivery_days > 3:
                is_deadline_feasible = False
                deadline_warning = f"Khách hàng cần gấp nhưng tiến độ vận hành kho cần {max_delivery_days} ngày để đủ hàng."

        return {
            "verified_items": verified_items,
            "unmatched_items": unmatched_items,
            "total_list_price": total_list_price,
            "has_stock_shortage": has_stock_shortage,
            "max_delivery_days": max_delivery_days,
            "is_deadline_feasible": is_deadline_feasible,
            "deadline_warning": deadline_warning
        }

    # =========================================================================
    # BƯỚC 6 & 7: LẬP BÁO GIÁ, KIỂM TRA THẨM QUYỀN & CHUYỂN TRƯỞNG PHÒNG DUYỆT
    # =========================================================================
    def evaluate_policy_and_discounts(
        self,
        total_list_price: float,
        requested_discount_pct: float,
        customer_budget: Optional[float]
    ) -> Dict[str, Any]:
        """
        Kiểm tra ma trận phân quyền phê duyệt chiết khấu của Công ty Minh An.
        - NVKD: Tối đa 5%
        - Trưởng phòng: Trên 5% đến 12%
        - Vượt 12%: Cần Giám đốc
        """
        disc_matrix = self.policies.get("discount_matrix", {})
        sales_max = disc_matrix.get("sales_rep_max_pct", 5.0)
        manager_max = disc_matrix.get("sales_manager_max_pct", 12.0)

        requires_manager = False
        requires_director = False
        approval_reasons = []

        # 1. Kiểm tra hạn mức chiết khấu
        if requested_discount_pct > sales_max:
            requires_manager = True
            approval_reasons.append(
                f"Đề xuất chiết khấu {requested_discount_pct}% vượt thẩm quyền NVKD (tối đa {sales_max}%)."
            )
        if requested_discount_pct > manager_max:
            requires_director = True
            approval_reasons.append(
                f"Đề xuất chiết khấu {requested_discount_pct}% vượt trần Trưởng phòng ({manager_max}%), cần Giám đốc thông qua."
            )

        # 2. Kiểm tra xung đột ngân sách
        applied_discount = requested_discount_pct
        discount_amount = total_list_price * (applied_discount / 100.0)
        final_quoted_price = total_list_price - discount_amount

        budget_alert = None
        if customer_budget and customer_budget > 0:
            if customer_budget < final_quoted_price:
                gap = final_quoted_price - customer_budget
                gap_pct = (gap / final_quoted_price) * 100.0
                budget_alert = (
                    f"Ngân sách khách hàng ({customer_budget:,.0f} VND) "
                    f"thấp hơn giá trị báo giá ({final_quoted_price:,.0f} VND) là {gap:,.0f} VND ({gap_pct:.1f}%)."
                )
                if gap_pct > 15.0:
                    requires_manager = True
                    approval_reasons.append(f"Chênh lệch ngân sách lớn ({gap_pct:.1f}%), cần xin ý kiến Trưởng phòng phương án tối ưu thiết bị.")

        return {
            "requested_discount_pct": requested_discount_pct,
            "applied_discount_pct": applied_discount,
            "discount_amount": discount_amount,
            "final_quoted_price": final_quoted_price,
            "requires_manager_approval": requires_manager,
            "requires_director_approval": requires_director,
            "approval_reasons": approval_reasons,
            "budget_alert": budget_alert
        }

    # =========================================================================
    # BƯỚC 8: SOẠN THẢO BẢN NHÁP BÁO GIÁ & ĐỀ XUẤT PHẢN HỒI
    # =========================================================================
    def generate_proposal_package(
        self,
        extracted: Dict[str, Any],
        assigned_rep: Dict[str, Any],
        audit_result: Dict[str, Any],
        policy_result: Dict[str, Any]
    ) -> Dict[str, Any]:
        customer = extracted.get("customer_name") or "Quý Khách hàng"
        company = extracted.get("company_name") or "Quý Doanh nghiệp"
        rep_name = assigned_rep.get("name", "NVKD")
        rep_phone = assigned_rep.get("phone", "0912.345.xxx")
        rep_email = assigned_rep.get("email", "sales@minhan-tech.vn")

        # Bảng chi tiết sản phẩm định dạng text
        item_rows = []
        for idx, it in enumerate(audit_result["verified_items"], 1):
            item_rows.append(
                f"  {idx}. {it['name']}\n"
                f"     - Số lượng: {it['quantity']} {it['unit']} | Đơn giá niêm yết: {it['unit_price']:,.0f} VND\n"
                f"     - Thành tiền: {it['line_total']:,.0f} VND\n"
                f"     - Tình trạng kho: {it['stock_status']}"
            )
        items_text = "\n".join(item_rows)

        # Ghi chú về thời hạn bàn giao
        if not audit_result["is_deadline_feasible"]:
            delivery_proposal_text = (
                f"LƯU Ý VỀ TIẾN ĐỘ BÀN GIAO:\n"
                f"Do một số hạng mục chuyên sâu cần thời gian nhập khẩu/kiểm định tiêu chuẩn ({audit_result['max_delivery_days']} ngày), "
                f"Minh An trân trọng đề xuất phương án 'Giao hàng 2 đợt' để đảm bảo không gián đoạn hoạt động của Quý công ty:\n"
                f"  • Đợt 1 (Trong 48h): Bàn giao các thiết bị đang có sẵn trong kho.\n"
                f"  • Đợt 2 (Sau {audit_result['max_delivery_days']} ngày): Bàn giao thiết bị còn lại và tiến hành nghiệm thu tổng thể."
            )
        else:
            delivery_proposal_text = (
                f"TIẾN ĐỘ BÀN GIAO DỰ KIẾN:\n"
                f"Toàn bộ thiết bị đều có sẵn trong kho Minh An. Thời gian bàn giao, cài đặt và bàn giao hoàn tất: "
                f"Trong vòng {audit_result['max_delivery_days']} ngày làm việc kể từ khi ký kết hợp đồng."
            )

        # Soạn nội dung email
        email_body = (
            f"Kính gửi: {customer} - {company},\n\n"
            f"Lời đầu tiên, Công ty Cổ phần Thiết bị & Dịch vụ Công nghệ Minh An xin gửi lời chào trân trọng "
            f"và cảm ơn Quý đơn vị đã quan tâm đến năng lực cung cấp giải pháp CNTT của chúng tôi.\n\n"
            f"Căn cứ vào yêu cầu từ Quý công ty, chuyên viên phụ trách {rep_name} xin trân trọng gửi bảng dự thảo đề xuất "
            f"và phương án giá ưu đãi dành riêng cho Quý doanh nghiệp như sau:\n\n"
            f"I. DANH MỤC THIẾT BỊ & GIẢI PHÁP ĐỀ XUẤT:\n"
            f"{items_text}\n\n"
            f"II. TỔNG HỢP GIÁ TRỊ DỰ TOÁN:\n"
            f"  • Tổng giá trị niêm yết: {audit_result['total_list_price']:,.0f} VND\n"
            f"  • Mức chiết khấu doanh nghiệp: {policy_result['applied_discount_pct']}% (-{policy_result['discount_amount']:,.0f} VND)\n"
            f"  • GIÁ TRỊ THANH TOÁN (Chưa VAT): {policy_result['final_quoted_price']:,.0f} VND\n"
            f"  (Giá đã bao gồm chi phí vận chuyển tận nơi và bảo hành chính hãng 12-36 tháng).\n\n"
            f"III. {delivery_proposal_text}\n\n"
            f"Hồ sơ chào giá chi tiết (file PDF có đóng dấu) cùng phương án kỹ thuật đã được NVKD chuẩn bị sẵn sàng. "
            f"Rất hân hạnh được sắp xếp một buổi trao đổi ngắn hoặc đến trực tiếp văn phòng Quý công ty để khảo sát và ký kết.\n\n"
            f"Mọi thắc mắc xin vui lòng liên hệ trực tiếp chuyên viên phụ trách:\n"
            f"Họ và tên: {rep_name}\n"
            f"Điện thoại: {rep_phone} | Email: {rep_email}\n\n"
            f"Kính chúc Quý công ty ngày càng phát triển và thịnh vượng!\n"
            f"Trân trọng,\n"
            f"Minh An Technology Services & Solutions"
        )

        # Thử nghiệm tối ưu hóa văn phong bằng Gemini nếu có kết nối
        if self.gemini:
            try:
                verified_items_summary = "\n".join([
                    f"- {it['name']}: {it['quantity']} {it['unit']} x {it['unit_price']:,.0f} VND = {it['line_total']:,.0f} VND (Tình trạng: {it['stock_status']})"
                    for it in audit_result["verified_items"]
                ])
                quote_summary = (
                    f"Tổng niêm yết: {audit_result['total_list_price']:,.0f} VND\n"
                    f"Chiết khấu: {policy_result['applied_discount_pct']}% (-{policy_result['discount_amount']:,.0f} VND)\n"
                    f"Giá thanh toán: {policy_result['final_quoted_price']:,.0f} VND"
                )
                email_body_llm = self.gemini.polish_response_email(
                    customer, company, rep_name, rep_phone, rep_email,
                    verified_items_summary, quote_summary, delivery_proposal_text
                )
                if email_body_llm and len(email_body_llm.strip()) > 50:
                    email_body = email_body_llm
            except Exception:
                pass

        # Lập Phiếu trình duyệt Trưởng phòng nếu cần
        internal_approval_memo = None
        if policy_result["requires_manager_approval"]:
            internal_approval_memo = {
                "title": f"PHIẾU TRÌNH PHÊ DUYỆT CƠ HỘI BÁN HÀNG - {company}",
                "urgency": "CAO" if not audit_result["is_deadline_feasible"] else "TRUNG BÌNH",
                "assigned_rep": rep_name,
                "reasons": policy_result["approval_reasons"],
                "total_list_price": audit_result["total_list_price"],
                "requested_discount": policy_result["requested_discount_pct"],
                "discount_amount": policy_result["discount_amount"],
                "final_amount": policy_result["final_quoted_price"],
                "budget_check": policy_result.get("budget_alert") or "Ngân sách phù hợp",
                "delivery_check": audit_result.get("deadline_warning") or "Tiến độ bình thường",
                "recommendation": (
                    f"NVKD {rep_name} đề xuất Trưởng phòng duyệt chiết khấu {policy_result['requested_discount_pct']}% "
                    f"để chốt đơn hàng trọng điểm {company}. "
                    f"{'Đề xuất cam kết giao đợt 1 hàng sẵn kho.' if not audit_result['is_deadline_feasible'] else ''}"
                )
            }

        return {
            "email_subject": f"[Minh An Tech] Thư chào giá & Đề xuất giải pháp thiết bị công nghệ - {company}",
            "email_body": email_body,
            "internal_approval_memo": internal_approval_memo
        }

    # =========================================================================
    # WORKFLOW CHÍNH (PIPELINE ĐIỀU PHỐI TOÀN DIỆN)
    # =========================================================================
    def process_request(
        self,
        raw_input_text: str,
        existing_opp_id: Optional[str] = None,
        override_fields: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Thực thi chuỗi xử lý khép kín bám sát chính xác sơ đồ mới của Minh An."""
        self.reload_data()
        now = datetime.now()
        timestamp_str = now.strftime("%Y-%m-%d %H:%M:%S")
        opp_id = existing_opp_id or f"OPP-{now.strftime('%Y%m%d')}-{abs(hash(raw_input_text + timestamp_str)) % 10000:04d}"

        # 1 & 2. Phân loại & Kiểm tra thông tin
        extracted = self.extract_and_classify(raw_input_text)

        # Nếu người dùng chỉnh sửa trực tiếp các ô nhập liệu trên giao diện (Interactive Step Inputs)
        if override_fields:
            for k in ["customer_name", "company_name", "email", "phone", "requested_deadline"]:
                if override_fields.get(k) is not None and str(override_fields.get(k)).strip() != "":
                    extracted[k] = str(override_fields[k]).strip()
            if override_fields.get("budget") is not None and str(override_fields.get("budget")).strip() != "":
                try:
                    extracted["budget"] = float(override_fields["budget"])
                except ValueError:
                    pass
            if override_fields.get("requested_discount_pct") is not None and str(override_fields.get("requested_discount_pct")).strip() != "":
                try:
                    extracted["requested_discount_pct"] = float(override_fields["requested_discount_pct"])
                except ValueError:
                    pass
            if override_fields.get("raw_items") is not None and isinstance(override_fields["raw_items"], list) and len(override_fields["raw_items"]) > 0:
                extracted["raw_items"] = override_fields["raw_items"]

            # Kiểm tra lại điều kiện đủ sau khi áp dụng override_fields
            missing = []
            if not extracted.get("email") and not extracted.get("phone"):
                missing.append("Thông tin liên lạc phản hồi (Email hoặc Số điện thoại người nhận)")
            if not extracted.get("raw_items"):
                missing.append("Danh sách cụ thể chủng loại thiết bị hoặc dịch vụ công nghệ cần báo giá")
            else:
                for it in extracted["raw_items"]:
                    if int(it.get("quantity", 0)) <= 0:
                        missing.append(f"Số lượng cần cung cấp cho hạng mục '{it.get('raw_name')}'")
            extracted["missing_fields"] = missing
            extracted["is_complete"] = len(missing) == 0

        # Quyết định 1: Có đủ thông tin cốt lõi? (Có liên hệ + Có SP & SL)
        if not extracted["is_complete"]:
            clarification = self.generate_clarification_request(extracted)
            result_record = {
                "id": opp_id,
                "created_at": timestamp_str,
                "raw_input_text": raw_input_text,
                "status": "CHỜ KH PHẢN HỒI BỔ SUNG",
                "status_code": "CLARIFICATION_REQUIRED",
                "send_locked": True,
                "flow_path": "1. Tiếp nhận -> 2. Phân loại -> Thiếu thông tin -> Nhánh 2B: Yêu cầu KH làm rõ -> Chờ KH phản hồi",
                "customer_name": extracted["customer_name"],
                "company_name": extracted["company_name"],
                "extracted_data": extracted,
                "clarification_package": clarification,
                "opportunity_profile": None,
                "proposal_package": None
            }
            self._save_to_pipeline(result_record)
            return result_record

        # Bước 3: Đủ thông tin -> Tạo Hồ sơ Cơ hội & Gán NVKD (hoặc giữ NVKD được chỉ định)
        assigned_rep = None
        if override_fields and override_fields.get("assigned_rep_id"):
            assigned_rep = next((r for r in self.sales_team if r["id"] == override_fields["assigned_rep_id"]), None)
        if not assigned_rep:
            assigned_rep = self.assign_sales_rep(extracted)

        # Bước 4: Thẩm định tồn kho & giá hiện hành
        audit_result = self.verify_inventory_and_pricing(
            extracted["raw_items"],
            extracted.get("requested_deadline")
        )

        # Bước 5: Lập báo giá & kiểm tra thẩm quyền
        policy_result = self.evaluate_policy_and_discounts(
            audit_result["total_list_price"],
            extracted.get("requested_discount_pct", 0.0),
            extracted.get("budget")
        )

        # Lập Đề xuất & Bản nháp
        proposal_pkg = self.generate_proposal_package(
            extracted, assigned_rep, audit_result, policy_result
        )

        # Xác định trạng thái khóa nút gửi theo thẩm quyền
        if policy_result["requires_manager_approval"]:
            final_status = "CHỜ TRƯỞNG PHÒNG DUYỆT (KHÓA GỬI)"
            status_code = "PENDING_APPROVAL"
            send_locked = True
            flow_path = "1. Tiếp nhận -> 2. Phân loại (Đủ) -> 3. Tạo Hồ sơ & Gán NVKD -> 4. Thẩm định kho & giá -> 5. Lập Báo giá -> Vượt thẩm quyền -> Trưởng phòng duyệt (Khóa nút gửi)"
        else:
            final_status = "SẴN SÀNG GỬI KH (READY_TO_SEND)"
            status_code = "READY_TO_SEND"
            send_locked = False
            flow_path = "1. Tiếp nhận -> 2. Phân loại (Đủ) -> 3. Tạo Hồ sơ & Gán NVKD -> 4. Thẩm định kho & giá -> 5. Lập Báo giá -> Đúng thẩm quyền -> EndTrack"

        opp_profile = {
            "opportunity_id": opp_id,
            "created_at": timestamp_str,
            "assigned_rep": assigned_rep,
            "customer_name": extracted["customer_name"],
            "company_name": extracted["company_name"],
            "email": extracted["email"],
            "phone": extracted["phone"],
            "budget": extracted["budget"],
            "requested_deadline": extracted["requested_deadline"],
            "inventory_audit": audit_result,
            "pricing_policy": policy_result
        }

        result_record = {
            "id": opp_id,
            "created_at": timestamp_str,
            "raw_input_text": raw_input_text,
            "status": final_status,
            "status_code": status_code,
            "send_locked": send_locked,
            "flow_path": flow_path,
            "customer_name": extracted["customer_name"],
            "company_name": extracted["company_name"],
            "assigned_rep_name": assigned_rep["name"],
            "total_amount": policy_result["final_quoted_price"],
            "extracted_data": extracted,
            "opportunity_profile": opp_profile,
            "proposal_package": proposal_pkg
        }

        self._save_to_pipeline(result_record)
        return result_record

    def approve_opportunity(self, opp_id: str, manager_notes: str = "Đã phê duyệt theo chính sách", approved_discount: Optional[float] = None) -> Dict[str, Any]:
        """Xử lý hành động Trưởng phòng duyệt trường hợp vượt quyền (Mở khóa nút gửi)."""
        records = load_json(PIPELINE_FILE, [])
        target = None
        for r in records:
            if r["id"] == opp_id:
                target = r
                break

        if not target:
            return {"success": False, "message": "Không tìm thấy hồ sơ cơ hội"}

        if approved_discount is not None and target.get("opportunity_profile"):
            opp = target["opportunity_profile"]
            total_list = opp["inventory_audit"]["total_list_price"]
            disc_amt = total_list * (float(approved_discount) / 100.0)
            final_price = total_list - disc_amt
            opp["pricing_policy"]["applied_discount_pct"] = float(approved_discount)
            opp["pricing_policy"]["discount_amount"] = disc_amt
            opp["pricing_policy"]["final_quoted_price"] = final_price
            opp["pricing_policy"]["requires_manager_approval"] = False
            target["total_amount"] = final_price

        target["status"] = "ĐÃ DUYỆT - MỞ KHÓA GỬI KH"
        target["status_code"] = "READY_TO_SEND"
        target["send_locked"] = False
        target["manager_review"] = {
            "reviewed_at": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "decision": "APPROVED",
            "notes": manager_notes
        }
        save_json(PIPELINE_FILE, records)
        return {"success": True, "record": target}

    def submit_customer_clarification(self, opp_id: str, reply_text: str, extra_fields: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Vòng lặp Nhánh 2B -> Chờ KH phản hồi -> Khách phản hồi xong -> Quay lại Bước 2: Phân loại & Kiểm tra.
        Gộp nội dung cũ + nội dung khách phản hồi bổ sung và chạy lại từ Bước 2.
        """
        records = load_json(PIPELINE_FILE, [])
        target_idx = None
        target = None
        for idx, r in enumerate(records):
            if r["id"] == opp_id:
                target_idx = idx
                target = r
                break

        combined_raw = (target.get("raw_input_text", "") if target else "") + "\n\n[KHÁCH HÀNG PHẢN HỒI BỔ SUNG]:\n" + reply_text
        new_result = self.process_request(combined_raw, existing_opp_id=opp_id, override_fields=extra_fields)
        new_result["clarification_loop_completed"] = True
        return new_result

    def mark_sent_endtrack(self, opp_id: str) -> Dict[str, Any]:
        """Bước cuối EndTrack: Xác nhận gửi báo giá/email cho khách hàng & đóng vòng lặp."""
        records = load_json(PIPELINE_FILE, [])
        for r in records:
            if r["id"] == opp_id:
                if r.get("status_code") == "PENDING_APPROVAL":
                    return {"success": False, "message": "Đơn hàng đang bị KHÓA gửi do chờ Trưởng phòng duyệt!"}
                r["status"] = "HOÀN TẤT (ENDTRACK - ĐÃ GỬI KH)"
                r["status_code"] = "ENDTRACK_COMPLETED"
                r["sent_at"] = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
                save_json(PIPELINE_FILE, records)
                return {"success": True, "record": r}
        return {"success": False, "message": "Không tìm thấy hồ sơ cơ hội"}

    def _save_to_pipeline(self, record: Dict[str, Any]):
        records = load_json(PIPELINE_FILE, [])
        records = [r for r in records if r.get("id") != record.get("id")]
        records.insert(0, record)
        if len(records) > 50:
            records = records[:50]
        save_json(PIPELINE_FILE, records)
