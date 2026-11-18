CREATE TABLE tenants (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	slug VARCHAR(80) NOT NULL, 
	shop_name VARCHAR(150) NOT NULL, 
	owner_name VARCHAR(150) NOT NULL, 
	email VARCHAR(150) NOT NULL, 
	phone VARCHAR(20), 
	gstin VARCHAR(20), 
	city VARCHAR(100), 
	address TEXT, 
	plan VARCHAR(50), 
	is_active BOOL NOT NULL, 
	email_verified BOOL, 
	email_verification_token VARCHAR(64), 
	created_at DATETIME, 
	PRIMARY KEY (id)
);
CREATE INDEX ix_tenants_id ON tenants (id);
CREATE UNIQUE INDEX ix_tenants_slug ON tenants (slug);
CREATE UNIQUE INDEX ix_tenants_email ON tenants (email);
CREATE TABLE medicines (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	tenant_id INTEGER, 
	particulars VARCHAR(255) NOT NULL, 
	normalized_name VARCHAR(255) NOT NULL, 
	unit VARCHAR(50), 
	mrp NUMERIC(10, 2), 
	net_rate NUMERIC(10, 2), 
	company VARCHAR(100), 
	stockist VARCHAR(100), 
	created_at DATETIME, 
	updated_at DATETIME, 
	current_stock NUMERIC(10, 2) NOT NULL, 
	low_stock_threshold NUMERIC(10, 2), 
	barcode VARCHAR(64), 
	composition VARCHAR(500), 
	lead_time_days INTEGER, 
	suggested_low_stock_threshold NUMERIC(10, 2), 
	avg_daily_sales_30d NUMERIC(10, 2), 
	suggestion_computed_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id)
);
CREATE UNIQUE INDEX ix_medicines_barcode ON medicines (barcode);
CREATE INDEX ix_medicines_id ON medicines (id);
CREATE INDEX ix_medicines_normalized_name ON medicines (normalized_name);
CREATE INDEX ix_medicines_tenant_id ON medicines (tenant_id);
CREATE TABLE distributors (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	tenant_id INTEGER, 
	name VARCHAR(150) NOT NULL, 
	gstin VARCHAR(20), 
	address VARCHAR(255), 
	phone VARCHAR(50), 
	PRIMARY KEY (id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id), 
	UNIQUE (name)
);
CREATE INDEX ix_distributors_id ON distributors (id);
CREATE INDEX ix_distributors_tenant_id ON distributors (tenant_id);
CREATE TABLE users (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	tenant_id INTEGER, 
	username VARCHAR(50) NOT NULL, 
	password_hash VARCHAR(255) NOT NULL, 
	full_name VARCHAR(100), 
	`role` ENUM('owner','staff') NOT NULL, 
	is_active BOOL, 
	created_at DATETIME, 
	whatsapp_number VARCHAR(20), 
	PRIMARY KEY (id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id)
);
CREATE INDEX ix_users_id ON users (id);
CREATE INDEX ix_users_tenant_id ON users (tenant_id);
CREATE UNIQUE INDEX ix_users_username ON users (username);
CREATE TABLE graph_edges (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	tenant_id INTEGER, 
	source_type VARCHAR(30) NOT NULL, 
	source_id VARCHAR(150) NOT NULL, 
	edge_type VARCHAR(30) NOT NULL, 
	target_type VARCHAR(30) NOT NULL, 
	target_id VARCHAR(150) NOT NULL, 
	weight NUMERIC(5, 2), 
	edge_metadata TEXT, 
	created_at DATETIME, 
	updated_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id)
);
CREATE INDEX ix_graph_edges_source_id ON graph_edges (source_id);
CREATE INDEX ix_graph_edges_source_type ON graph_edges (source_type);
CREATE INDEX ix_graph_edges_id ON graph_edges (id);
CREATE INDEX ix_graph_edges_tenant_id ON graph_edges (tenant_id);
CREATE INDEX ix_graph_edges_edge_type ON graph_edges (edge_type);
CREATE INDEX ix_graph_edges_target_id ON graph_edges (target_id);
CREATE TABLE audit_ledger (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	tenant_id INTEGER, 
	event_type VARCHAR(50) NOT NULL, 
	reference_id INTEGER, 
	payload_json TEXT NOT NULL, 
	payload_hash VARCHAR(64) NOT NULL, 
	previous_hash VARCHAR(64) NOT NULL, 
	entry_hash VARCHAR(64) NOT NULL, 
	created_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id)
);
CREATE INDEX ix_audit_ledger_tenant_id ON audit_ledger (tenant_id);
CREATE INDEX ix_audit_ledger_created_at ON audit_ledger (created_at);
CREATE INDEX ix_audit_ledger_id ON audit_ledger (id);
CREATE UNIQUE INDEX ix_audit_ledger_entry_hash ON audit_ledger (entry_hash);
CREATE INDEX ix_audit_ledger_event_type ON audit_ledger (event_type);
CREATE INDEX ix_audit_ledger_reference_id ON audit_ledger (reference_id);
CREATE TABLE customers (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	tenant_id INTEGER, 
	phone VARCHAR(15) NOT NULL, 
	name VARCHAR(100), 
	consent_given_at DATETIME, 
	created_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id)
);
CREATE INDEX ix_customers_id ON customers (id);
CREATE UNIQUE INDEX ix_customers_phone ON customers (phone);
CREATE INDEX ix_customers_tenant_id ON customers (tenant_id);
CREATE TABLE pharmacy_nodes (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	tenant_id INTEGER, 
	shop_name VARCHAR(150) NOT NULL, 
	api_base_url VARCHAR(255), 
	contact_phone VARCHAR(50), 
	is_self BOOL, 
	opted_in BOOL, 
	joined_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id)
);
CREATE INDEX ix_pharmacy_nodes_id ON pharmacy_nodes (id);
CREATE INDEX ix_pharmacy_nodes_tenant_id ON pharmacy_nodes (tenant_id);
CREATE TABLE surveillance_daily_counts (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	tenant_id INTEGER, 
	condition_name VARCHAR(150) NOT NULL, 
	count_date DATE NOT NULL, 
	otc_units INTEGER NOT NULL, 
	created_at DATETIME, 
	updated_at DATETIME, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_surveillance_daily_counts_cond_date UNIQUE (condition_name, count_date), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id)
);
CREATE INDEX ix_surveillance_daily_counts_id ON surveillance_daily_counts (id);
CREATE INDEX ix_surveillance_daily_counts_count_date ON surveillance_daily_counts (count_date);
CREATE INDEX ix_surveillance_daily_counts_condition_name ON surveillance_daily_counts (condition_name);
CREATE INDEX ix_surveillance_daily_counts_tenant_id ON surveillance_daily_counts (tenant_id);
CREATE TABLE cold_chain_units (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	tenant_id INTEGER, 
	unit_label VARCHAR(100) NOT NULL, 
	location_note VARCHAR(255), 
	min_temp_c NUMERIC(5, 2) NOT NULL, 
	max_temp_c NUMERIC(5, 2) NOT NULL, 
	is_active BOOL, 
	created_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id), 
	UNIQUE (unit_label)
);
CREATE INDEX ix_cold_chain_units_tenant_id ON cold_chain_units (tenant_id);
CREATE INDEX ix_cold_chain_units_id ON cold_chain_units (id);
CREATE TABLE bills (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	tenant_id INTEGER, 
	distributor_id INTEGER, 
	invoice_no VARCHAR(100), 
	invoice_date DATETIME, 
	year INTEGER, 
	month INTEGER, 
	image_path VARCHAR(500), 
	total_amount NUMERIC(10, 2), 
	status ENUM('queued','processing','pending_review','needs_attention','confirmed','rejected','failed'), 
	uploaded_at DATETIME, 
	raw_ocr_text TEXT, 
	celery_task_id VARCHAR(100), 
	processing_error TEXT, 
	ocr_confidence NUMERIC(5, 2), 
	needs_attention_reason VARCHAR(255), 
	preprocessing_notes TEXT, 
	checksum VARCHAR(64), 
	PRIMARY KEY (id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id), 
	FOREIGN KEY(distributor_id) REFERENCES distributors (id)
);
CREATE INDEX ix_bills_id ON bills (id);
CREATE INDEX ix_bills_year ON bills (year);
CREATE INDEX ix_bills_checksum ON bills (checksum);
CREATE INDEX ix_bills_month ON bills (month);
CREATE INDEX ix_bills_celery_task_id ON bills (celery_task_id);
CREATE INDEX ix_bills_tenant_id ON bills (tenant_id);
CREATE TABLE user_mappings (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	tenant_id INTEGER, 
	distributor_id INTEGER, 
	raw_name VARCHAR(255) NOT NULL, 
	medicine_id INTEGER NOT NULL, 
	created_at DATETIME, 
	updated_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id), 
	FOREIGN KEY(distributor_id) REFERENCES distributors (id), 
	FOREIGN KEY(medicine_id) REFERENCES medicines (id)
);
CREATE INDEX ix_user_mappings_raw_name ON user_mappings (raw_name);
CREATE INDEX ix_user_mappings_distributor_id ON user_mappings (distributor_id);
CREATE INDEX ix_user_mappings_id ON user_mappings (id);
CREATE INDEX ix_user_mappings_tenant_id ON user_mappings (tenant_id);
CREATE TABLE sales (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	tenant_id INTEGER, 
	medicine_id INTEGER NOT NULL, 
	qty_sold NUMERIC(10, 2) NOT NULL, 
	sold_at DATETIME, 
	customer_id INTEGER, 
	PRIMARY KEY (id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id), 
	FOREIGN KEY(medicine_id) REFERENCES medicines (id), 
	FOREIGN KEY(customer_id) REFERENCES customers (id)
);
CREATE INDEX ix_sales_tenant_id ON sales (tenant_id);
CREATE INDEX ix_sales_medicine_id ON sales (medicine_id);
CREATE INDEX ix_sales_id ON sales (id);
CREATE INDEX ix_sales_customer_id ON sales (customer_id);
CREATE TABLE reorder_items (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	tenant_id INTEGER, 
	medicine_id INTEGER, 
	custom_name VARCHAR(255), 
	distributor_id INTEGER, 
	quantity_needed NUMERIC(10, 2), 
	note VARCHAR(255), 
	source ENUM('auto_low_stock','manual'), 
	fulfilled BOOL, 
	created_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id), 
	FOREIGN KEY(medicine_id) REFERENCES medicines (id), 
	FOREIGN KEY(distributor_id) REFERENCES distributors (id)
);
CREATE INDEX ix_reorder_items_tenant_id ON reorder_items (tenant_id);
CREATE INDEX ix_reorder_items_id ON reorder_items (id);
CREATE TABLE refresh_tokens (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	tenant_id INTEGER, 
	user_id INTEGER NOT NULL, 
	token_hash VARCHAR(64) NOT NULL, 
	expires_at DATETIME NOT NULL, 
	revoked BOOL NOT NULL, 
	created_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id), 
	FOREIGN KEY(user_id) REFERENCES users (id)
);
CREATE INDEX ix_refresh_tokens_user_id ON refresh_tokens (user_id);
CREATE UNIQUE INDEX ix_refresh_tokens_token_hash ON refresh_tokens (token_hash);
CREATE INDEX ix_refresh_tokens_id ON refresh_tokens (id);
CREATE INDEX ix_refresh_tokens_tenant_id ON refresh_tokens (tenant_id);
CREATE TABLE medicine_salts (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	tenant_id INTEGER, 
	medicine_id INTEGER NOT NULL, 
	salt_name VARCHAR(150) NOT NULL, 
	strength VARCHAR(50), 
	PRIMARY KEY (id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id), 
	FOREIGN KEY(medicine_id) REFERENCES medicines (id)
);
CREATE INDEX ix_medicine_salts_id ON medicine_salts (id);
CREATE INDEX ix_medicine_salts_medicine_id ON medicine_salts (medicine_id);
CREATE INDEX ix_medicine_salts_salt_name ON medicine_salts (salt_name);
CREATE INDEX ix_medicine_salts_tenant_id ON medicine_salts (tenant_id);
CREATE TABLE notifications (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	tenant_id INTEGER, 
	recipient_user_id INTEGER, 
	notification_type ENUM('adherence_overdue','anomaly_flagged','low_stock_crossed','credit_overdue','trust_chain_tamper','near_expiry','daily_digest','system') NOT NULL, 
	title VARCHAR(255) NOT NULL, 
	body TEXT NOT NULL, 
	severity ENUM('info','warning','critical') NOT NULL, 
	related_entity_type VARCHAR(50), 
	related_entity_id VARCHAR(50), 
	channel ENUM('in_app','whatsapp','sms','email') NOT NULL, 
	is_read BOOL NOT NULL, 
	sent_at DATETIME, 
	created_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id), 
	FOREIGN KEY(recipient_user_id) REFERENCES users (id)
);
CREATE INDEX ix_notifications_id ON notifications (id);
CREATE INDEX ix_notifications_notification_type ON notifications (notification_type);
CREATE INDEX ix_notifications_recipient_user_id ON notifications (recipient_user_id);
CREATE INDEX ix_notifications_tenant_id ON notifications (tenant_id);
CREATE TABLE cold_chain_readings (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	tenant_id INTEGER, 
	unit_id INTEGER NOT NULL, 
	recorded_temp_c NUMERIC(5, 2) NOT NULL, 
	recorded_by_user_id INTEGER, 
	recorded_at DATETIME NOT NULL, 
	note VARCHAR(255), 
	is_excursion BOOL NOT NULL, 
	PRIMARY KEY (id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id), 
	FOREIGN KEY(unit_id) REFERENCES cold_chain_units (id), 
	FOREIGN KEY(recorded_by_user_id) REFERENCES users (id)
);
CREATE INDEX ix_cold_chain_readings_unit_id ON cold_chain_readings (unit_id);
CREATE INDEX ix_cold_chain_readings_id ON cold_chain_readings (id);
CREATE INDEX ix_cold_chain_readings_recorded_at ON cold_chain_readings (recorded_at);
CREATE INDEX ix_cold_chain_readings_tenant_id ON cold_chain_readings (tenant_id);
CREATE INDEX ix_cold_chain_readings_recorded_by_user_id ON cold_chain_readings (recorded_by_user_id);
CREATE TABLE distributor_trust_scores (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	tenant_id INTEGER, 
	distributor_id INTEGER NOT NULL, 
	medicine_id INTEGER, 
	score NUMERIC(5, 2) NOT NULL, 
	confidence VARCHAR(20) NOT NULL, 
	computed_at DATETIME, 
	PRIMARY KEY (id), 
	CONSTRAINT uq_distributor_trust_score UNIQUE (distributor_id, medicine_id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id), 
	FOREIGN KEY(distributor_id) REFERENCES distributors (id), 
	FOREIGN KEY(medicine_id) REFERENCES medicines (id)
);
CREATE INDEX ix_distributor_trust_scores_id ON distributor_trust_scores (id);
CREATE INDEX ix_distributor_trust_scores_tenant_id ON distributor_trust_scores (tenant_id);
CREATE INDEX ix_distributor_trust_scores_medicine_id ON distributor_trust_scores (medicine_id);
CREATE INDEX ix_distributor_trust_scores_distributor_id ON distributor_trust_scores (distributor_id);
CREATE TABLE prescriptions (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	tenant_id INTEGER, 
	customer_id INTEGER, 
	image_path VARCHAR(500) NOT NULL, 
	status ENUM('queued','processing','ready','converted','abandoned') NOT NULL, 
	converted_to_sale BOOL NOT NULL, 
	purchased_at DATETIME, 
	raw_ocr_text TEXT, 
	ocr_confidence NUMERIC(5, 2), 
	doctor_name VARCHAR(150), 
	clinic_name VARCHAR(200), 
	processing_error TEXT, 
	created_at DATETIME, 
	updated_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id), 
	FOREIGN KEY(customer_id) REFERENCES customers (id)
);
CREATE INDEX ix_prescriptions_tenant_id ON prescriptions (tenant_id);
CREATE INDEX ix_prescriptions_status ON prescriptions (status);
CREATE INDEX ix_prescriptions_id ON prescriptions (id);
CREATE INDEX ix_prescriptions_customer_id ON prescriptions (customer_id);
CREATE INDEX ix_prescriptions_created_at ON prescriptions (created_at);
CREATE TABLE bill_items (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	tenant_id INTEGER, 
	bill_id INTEGER NOT NULL, 
	medicine_id INTEGER, 
	raw_name VARCHAR(255) NOT NULL, 
	pack VARCHAR(50), 
	batch VARCHAR(50), 
	exp_date VARCHAR(20), 
	qty NUMERIC(10, 2), 
	free_qty NUMERIC(10, 2), 
	mrp NUMERIC(10, 2), 
	rate NUMERIC(10, 2), 
	discount_pct NUMERIC(5, 2), 
	special_discount_pct NUMERIC(5, 2), 
	gst_pct NUMERIC(5, 2), 
	amount NUMERIC(10, 2), 
	computed_cost_per_unit NUMERIC(10, 2), 
	match_confidence NUMERIC(5, 2), 
	match_status ENUM('auto','learned','manual','unmatched','confirmed'), 
	PRIMARY KEY (id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id), 
	FOREIGN KEY(bill_id) REFERENCES bills (id), 
	FOREIGN KEY(medicine_id) REFERENCES medicines (id)
);
CREATE INDEX ix_bill_items_id ON bill_items (id);
CREATE INDEX ix_bill_items_tenant_id ON bill_items (tenant_id);
CREATE TABLE customer_credit_ledger (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	tenant_id INTEGER, 
	customer_id INTEGER NOT NULL, 
	change_amount NUMERIC(10, 2) NOT NULL, 
	resulting_balance NUMERIC(10, 2) NOT NULL, 
	reason ENUM('credit_sale','payment_received','adjustment') NOT NULL, 
	reference_sale_id INTEGER, 
	note VARCHAR(255), 
	created_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id), 
	FOREIGN KEY(customer_id) REFERENCES customers (id), 
	FOREIGN KEY(reference_sale_id) REFERENCES sales (id)
);
CREATE INDEX ix_customer_credit_ledger_id ON customer_credit_ledger (id);
CREATE INDEX ix_customer_credit_ledger_customer_id ON customer_credit_ledger (customer_id);
CREATE INDEX ix_customer_credit_ledger_tenant_id ON customer_credit_ledger (tenant_id);
CREATE TABLE prescription_items (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	tenant_id INTEGER, 
	prescription_id INTEGER NOT NULL, 
	medicine_id INTEGER, 
	substitute_medicine_id INTEGER, 
	raw_name VARCHAR(255) NOT NULL, 
	qty_prescribed NUMERIC(10, 2), 
	dosage_instructions VARCHAR(255), 
	match_confidence NUMERIC(5, 2), 
	match_status ENUM('auto','learned','manual','unmatched'), 
	in_stock BOOL, 
	current_stock_qty NUMERIC(10, 2), 
	added_to_cart BOOL NOT NULL, 
	created_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id), 
	FOREIGN KEY(prescription_id) REFERENCES prescriptions (id), 
	FOREIGN KEY(medicine_id) REFERENCES medicines (id), 
	FOREIGN KEY(substitute_medicine_id) REFERENCES medicines (id)
);
CREATE INDEX ix_prescription_items_id ON prescription_items (id);
CREATE INDEX ix_prescription_items_tenant_id ON prescription_items (tenant_id);
CREATE INDEX ix_prescription_items_prescription_id ON prescription_items (prescription_id);
CREATE INDEX ix_prescription_items_medicine_id ON prescription_items (medicine_id);
CREATE TABLE rate_history (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	tenant_id INTEGER, 
	medicine_id INTEGER NOT NULL, 
	bill_item_id INTEGER, 
	old_net_rate NUMERIC(10, 2), 
	new_net_rate NUMERIC(10, 2), 
	old_mrp NUMERIC(10, 2), 
	new_mrp NUMERIC(10, 2), 
	changed_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id), 
	FOREIGN KEY(medicine_id) REFERENCES medicines (id), 
	FOREIGN KEY(bill_item_id) REFERENCES bill_items (id)
);
CREATE INDEX ix_rate_history_id ON rate_history (id);
CREATE INDEX ix_rate_history_tenant_id ON rate_history (tenant_id);
CREATE TABLE stock_ledger (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	tenant_id INTEGER, 
	medicine_id INTEGER NOT NULL, 
	change_qty NUMERIC(10, 2) NOT NULL, 
	resulting_balance NUMERIC(10, 2) NOT NULL, 
	reason ENUM('bill_received','sale','manual_adjustment') NOT NULL, 
	reference_bill_item_id INTEGER, 
	reference_sale_id INTEGER, 
	note VARCHAR(255), 
	created_by_user_id INTEGER, 
	created_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id), 
	FOREIGN KEY(medicine_id) REFERENCES medicines (id), 
	FOREIGN KEY(reference_bill_item_id) REFERENCES bill_items (id), 
	FOREIGN KEY(reference_sale_id) REFERENCES sales (id), 
	FOREIGN KEY(created_by_user_id) REFERENCES users (id)
);
CREATE INDEX ix_stock_ledger_medicine_id ON stock_ledger (medicine_id);
CREATE INDEX ix_stock_ledger_created_by_user_id ON stock_ledger (created_by_user_id);
CREATE INDEX ix_stock_ledger_id ON stock_ledger (id);
CREATE INDEX ix_stock_ledger_tenant_id ON stock_ledger (tenant_id);
CREATE TABLE medicine_batches (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	tenant_id INTEGER, 
	medicine_id INTEGER NOT NULL, 
	batch_no VARCHAR(50), 
	expiry_date DATE, 
	qty_received NUMERIC(10, 2) NOT NULL, 
	bill_item_id INTEGER, 
	distributor_id INTEGER, 
	is_cold_chain BOOL, 
	created_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id), 
	FOREIGN KEY(medicine_id) REFERENCES medicines (id), 
	UNIQUE (bill_item_id), 
	FOREIGN KEY(bill_item_id) REFERENCES bill_items (id), 
	FOREIGN KEY(distributor_id) REFERENCES distributors (id)
);
CREATE INDEX ix_medicine_batches_medicine_id ON medicine_batches (medicine_id);
CREATE INDEX ix_medicine_batches_tenant_id ON medicine_batches (tenant_id);
CREATE INDEX ix_medicine_batches_id ON medicine_batches (id);
CREATE INDEX ix_medicine_batches_expiry_date ON medicine_batches (expiry_date);
CREATE TABLE network_listings (
	id INTEGER NOT NULL AUTO_INCREMENT, 
	tenant_id INTEGER, 
	pharmacy_node_id INTEGER NOT NULL, 
	listing_type ENUM('near_expiry','excess_stock','shortage_request') NOT NULL, 
	medicine_name VARCHAR(255) NOT NULL, 
	composition VARCHAR(500), 
	quantity NUMERIC(10, 2), 
	expiry_date DATE, 
	note VARCHAR(255), 
	status ENUM('open','claimed','fulfilled','withdrawn') NOT NULL, 
	claimed_by_node_id INTEGER, 
	source_batch_id INTEGER, 
	created_at DATETIME, 
	updated_at DATETIME, 
	PRIMARY KEY (id), 
	FOREIGN KEY(tenant_id) REFERENCES tenants (id), 
	FOREIGN KEY(pharmacy_node_id) REFERENCES pharmacy_nodes (id), 
	FOREIGN KEY(claimed_by_node_id) REFERENCES pharmacy_nodes (id), 
	FOREIGN KEY(source_batch_id) REFERENCES medicine_batches (id)
);
CREATE INDEX ix_network_listings_id ON network_listings (id);
CREATE INDEX ix_network_listings_pharmacy_node_id ON network_listings (pharmacy_node_id);
CREATE INDEX ix_network_listings_status ON network_listings (status);
CREATE INDEX ix_network_listings_tenant_id ON network_listings (tenant_id);
CREATE INDEX ix_network_listings_listing_type ON network_listings (listing_type);
