# --- UPDATED ALLOTMENT TOOLS WITH WHATSAPP LINK ---
with st.sidebar:
    if pwd == "GeimsAdmin99":
        st.subheader("🔑 Allotment Tools")
        waiting = [r for r in req_list if not r.get('bed_no') and r.get('status') == "WAITING"]
        
        if waiting:
            p_sel = st.selectbox("Assign Patient", [r['name'] for r in waiting])
            b_val = st.text_input("Assign Bed No.")
            
            # WhatsApp Number for the Ward (Change this to the Ward's phone number)
            ward_phone = st.text_input("Ward Phone Number", value="91XXXXXXXXXX")
            
            if st.button("Finalize Allotment"):
                r_id = next(r['ID'] for r in waiting if r['name'] == p_sel)
                
                # Atomic Batch Update
                batch = db.batch()
                batch.update(db.collection("bed_requests").document(r_id), {"bed_no": b_val, "status": "DONE"})
                if b_val in all_bed_ids:
                    batch.set(db.collection("beds").document(b_val), {"status": "ALLOTTED", "patient": p_sel})
                batch.commit()
                
                # Create WhatsApp Message
                msg = f"🏥 *GEIMS Shifting Alert*\n\n" \
                      f"Patient: *{p_sel}*\n" \
                      f"Allotted Bed: *{b_val}*\n" \
                      f"Date: {datetime.now(tz).strftime('%d/%m/%Y')}\n\n" \
                      f"M.O.D: {st.session_state.get('user_name', 'Anuj Gill')}\n" \
                      f"Please prepare for shifting."
                
                # Encode for URL
                from urllib.parse import quote
                wa_link = f"https://wa.me/{ward_phone}?text={quote(msg)}"
                
                st.success(f"Allotted {b_val} to {p_sel}!")
                st.markdown(f'''
                    <a href="{wa_link}" target="_blank">
                        <button style="background-color:#25D366; color:white; border:none; padding:10px 20px; border-radius:5px; cursor:pointer; width:100%;">
                            📲 Send WhatsApp to Ward
                        </button>
                    </a>
                ''', unsafe_allow_html=True)
                
                st.cache_data.clear()
