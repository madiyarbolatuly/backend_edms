--
-- PostgreSQL database dump
--

-- Dumped from database version 17.5 (Debian 17.5-1.pgdg120+1)
-- Dumped by pg_dump version 17.5 (Debian 17.5-1.pgdg120+1)

SET statement_timeout = 0;
SET lock_timeout = 0;
SET idle_in_transaction_session_timeout = 0;
SET transaction_timeout = 0;
SET client_encoding = 'UTF8';
SET standard_conforming_strings = on;
SELECT pg_catalog.set_config('search_path', '', false);
SET check_function_bodies = false;
SET xmloption = content;
SET client_min_messages = warning;
SET row_security = off;

--
-- Name: pgcrypto; Type: EXTENSION; Schema: -; Owner: -
--

CREATE EXTENSION IF NOT EXISTS pgcrypto WITH SCHEMA public;


--
-- Name: EXTENSION pgcrypto; Type: COMMENT; Schema: -; Owner: 
--

COMMENT ON EXTENSION pgcrypto IS 'cryptographic functions';


--
-- Name: accesslevel; Type: TYPE; Schema: public; Owner: postgres
--

CREATE TYPE public.accesslevel AS ENUM (
    'read',
    'write',
    'admin'
);


ALTER TYPE public.accesslevel OWNER TO postgres;

--
-- Name: docstatus; Type: TYPE; Schema: public; Owner: postgres
--

CREATE TYPE public.docstatus AS ENUM (
    'public',
    'private',
    'shared',
    'deleted',
    'archived',
    'draft',
    'review',
    'published'
);


ALTER TYPE public.docstatus OWNER TO postgres;

--
-- Name: notifyenum; Type: TYPE; Schema: public; Owner: postgres
--

CREATE TYPE public.notifyenum AS ENUM (
    'read',
    'unread'
);


ALTER TYPE public.notifyenum OWNER TO postgres;

--
-- Name: userrole; Type: TYPE; Schema: public; Owner: postgres
--

CREATE TYPE public.userrole AS ENUM (
    'admin',
    'editor',
    'viewer'
);


ALTER TYPE public.userrole OWNER TO postgres;

SET default_tablespace = '';

SET default_table_access_method = heap;

--
-- Name: departments; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.departments (
    id integer NOT NULL,
    tenant_id integer NOT NULL,
    name character varying NOT NULL,
    created_at timestamp with time zone NOT NULL
);


ALTER TABLE public.departments OWNER TO postgres;

--
-- Name: departments_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.departments_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.departments_id_seq OWNER TO postgres;

--
-- Name: departments_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.departments_id_seq OWNED BY public.departments.id;


--
-- Name: document_tags; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.document_tags (
    id integer NOT NULL,
    document_id integer NOT NULL,
    tag_id integer NOT NULL
);


ALTER TABLE public.document_tags OWNER TO postgres;

--
-- Name: document_tags_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.document_tags_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.document_tags_id_seq OWNER TO postgres;

--
-- Name: document_tags_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.document_tags_id_seq OWNED BY public.document_tags.id;


--
-- Name: document_versions; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.document_versions (
    id integer NOT NULL,
    document_id integer NOT NULL,
    version_number integer NOT NULL,
    file_path character varying NOT NULL,
    created_at timestamp with time zone NOT NULL
);


ALTER TABLE public.document_versions OWNER TO postgres;

--
-- Name: document_versions_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.document_versions_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.document_versions_id_seq OWNER TO postgres;

--
-- Name: document_versions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.document_versions_id_seq OWNED BY public.document_versions.id;


--
-- Name: documents; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.documents (
    id integer NOT NULL,
    tenant_id integer NOT NULL,
    department_id integer NOT NULL,
    owner_id character varying(255) NOT NULL,
    file_type character varying(255) DEFAULT 'file'::character varying NOT NULL,
    document_number character varying NOT NULL,
    title character varying NOT NULL,
    name character varying NOT NULL,
    status public.docstatus NOT NULL,
    file_path character varying NOT NULL,
    is_archived boolean NOT NULL,
    is_favourited boolean NOT NULL,
    file_hash character varying,
    created_at timestamp with time zone NOT NULL,
    deleted_at timestamp with time zone,
    parent_id integer
);


ALTER TABLE public.documents OWNER TO postgres;

--
-- Name: documents_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.documents_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.documents_id_seq OWNER TO postgres;

--
-- Name: documents_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.documents_id_seq OWNED BY public.documents.id;


--
-- Name: notify; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.notify (
    id uuid NOT NULL,
    user_id character varying(255) NOT NULL,
    message text NOT NULL,
    type public.notifyenum NOT NULL,
    status public.notifyenum,
    created_at timestamp with time zone NOT NULL
);


ALTER TABLE public.notify OWNER TO postgres;

--
-- Name: permissions; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.permissions (
    id integer NOT NULL,
    document_id integer NOT NULL,
    user_id character varying(255) NOT NULL,
    access_level public.accesslevel NOT NULL,
    created_at timestamp with time zone NOT NULL
);


ALTER TABLE public.permissions OWNER TO postgres;

--
-- Name: permissions_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.permissions_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.permissions_id_seq OWNER TO postgres;

--
-- Name: permissions_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.permissions_id_seq OWNED BY public.permissions.id;


--
-- Name: shared_documents; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.shared_documents (
    id integer NOT NULL,
    document_id integer NOT NULL,
    shared_by character varying(255) NOT NULL,
    shared_with character varying(255) NOT NULL,
    token character varying NOT NULL,
    filename character varying NOT NULL,
    created_at timestamp with time zone NOT NULL,
    expires_at timestamp with time zone
);


ALTER TABLE public.shared_documents OWNER TO postgres;

--
-- Name: shared_documents_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.shared_documents_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.shared_documents_id_seq OWNER TO postgres;

--
-- Name: shared_documents_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.shared_documents_id_seq OWNED BY public.shared_documents.id;


--
-- Name: tags; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.tags (
    id integer NOT NULL,
    name character varying NOT NULL,
    created_at timestamp with time zone NOT NULL
);


ALTER TABLE public.tags OWNER TO postgres;

--
-- Name: tags_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.tags_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.tags_id_seq OWNER TO postgres;

--
-- Name: tags_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.tags_id_seq OWNED BY public.tags.id;


--
-- Name: tenants; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.tenants (
    id integer NOT NULL,
    name character varying NOT NULL,
    created_at timestamp with time zone NOT NULL
);


ALTER TABLE public.tenants OWNER TO postgres;

--
-- Name: tenants_id_seq; Type: SEQUENCE; Schema: public; Owner: postgres
--

CREATE SEQUENCE public.tenants_id_seq
    AS integer
    START WITH 1
    INCREMENT BY 1
    NO MINVALUE
    NO MAXVALUE
    CACHE 1;


ALTER SEQUENCE public.tenants_id_seq OWNER TO postgres;

--
-- Name: tenants_id_seq; Type: SEQUENCE OWNED BY; Schema: public; Owner: postgres
--

ALTER SEQUENCE public.tenants_id_seq OWNED BY public.tenants.id;


--
-- Name: users; Type: TABLE; Schema: public; Owner: postgres
--

CREATE TABLE public.users (
    id character varying(255) NOT NULL,
    tenant_id integer NOT NULL,
    department_id integer NOT NULL,
    username character varying NOT NULL,
    email character varying NOT NULL,
    password character varying NOT NULL,
    role public.userrole NOT NULL,
    is_active boolean NOT NULL,
    created_at timestamp with time zone NOT NULL
);


ALTER TABLE public.users OWNER TO postgres;

--
-- Name: departments id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.departments ALTER COLUMN id SET DEFAULT nextval('public.departments_id_seq'::regclass);


--
-- Name: document_tags id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.document_tags ALTER COLUMN id SET DEFAULT nextval('public.document_tags_id_seq'::regclass);


--
-- Name: document_versions id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.document_versions ALTER COLUMN id SET DEFAULT nextval('public.document_versions_id_seq'::regclass);


--
-- Name: documents id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.documents ALTER COLUMN id SET DEFAULT nextval('public.documents_id_seq'::regclass);


--
-- Name: permissions id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.permissions ALTER COLUMN id SET DEFAULT nextval('public.permissions_id_seq'::regclass);


--
-- Name: shared_documents id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.shared_documents ALTER COLUMN id SET DEFAULT nextval('public.shared_documents_id_seq'::regclass);


--
-- Name: tags id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.tags ALTER COLUMN id SET DEFAULT nextval('public.tags_id_seq'::regclass);


--
-- Name: tenants id; Type: DEFAULT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.tenants ALTER COLUMN id SET DEFAULT nextval('public.tenants_id_seq'::regclass);


--
-- Data for Name: departments; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.departments (id, tenant_id, name, created_at) FROM stdin;
1	1	GQ Contract	2025-08-20 09:44:10.34583+00
\.


--
-- Data for Name: document_tags; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.document_tags (id, document_id, tag_id) FROM stdin;
\.


--
-- Data for Name: document_versions; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.document_versions (id, document_id, version_number, file_path, created_at) FROM stdin;
\.


--
-- Data for Name: documents; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.documents (id, tenant_id, department_id, owner_id, file_type, document_number, title, name, status, file_path, is_archived, is_favourited, file_hash, created_at, deleted_at, parent_id) FROM stdin;
2902	1	1	c17ba46f-b4b0-473c-ac93-cb10cfed0f7e	folder	b6edaf0f-0499-4f01-9565-b9aad483d419	ПГУ	ПГУ	private	1/1/ПГУ	f	f	\N	2025-09-04 13:27:09.508703+00	\N	\N
2929	1	1	c17ba46f-b4b0-473c-ac93-cb10cfed0f7e	file	6dc79d02-4c0e-46b7-8857-96ec62b2df97	ПГУ.rar	ПГУ.rar	draft	1/1/ПГУ/ПГУ.rar	f	f	manualhash1234567890	2025-09-04 13:27:31.684881+00	\N	2902
\.


--
-- Data for Name: notify; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.notify (id, user_id, message, type, status, created_at) FROM stdin;
\.


--
-- Data for Name: permissions; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.permissions (id, document_id, user_id, access_level, created_at) FROM stdin;
\.


--
-- Data for Name: shared_documents; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.shared_documents (id, document_id, shared_by, shared_with, token, filename, created_at, expires_at) FROM stdin;
\.


--
-- Data for Name: tags; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.tags (id, name, created_at) FROM stdin;
\.


--
-- Data for Name: tenants; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.tenants (id, name, created_at) FROM stdin;
1	GQ Group	2025-08-20 09:40:42.745791+00
2	GQ Contract	2025-08-20 09:40:42.745791+00
3	GQ Group Invest	2025-08-20 09:40:42.745791+00
\.


--
-- Data for Name: users; Type: TABLE DATA; Schema: public; Owner: postgres
--

COPY public.users (id, tenant_id, department_id, username, email, password, role, is_active, created_at) FROM stdin;
01K33DTSJ92FF4FRAKW0TRTWYE	1	1	admin	admin@example.com	$2b$12$/6SdEaqLf7dzrZvNrHehau2rn0x6OamQAo8nyz06LTkc20mpD.OWK	admin	t	2025-08-20 09:31:23.251802+00
595f45da-43d6-4704-9efc-866692708b43	1	1	anargul.kashabayeva	a.kashabayeva@gqgroup.kz	$2a$06$WqEhmBrNenTN7vAFMyKCCuCYqQh182UuSeoiLLMvAXi43H00GORO.	editor	t	2025-08-20 09:50:56.582585+00
af301f84-5072-4c8e-bca9-339e3419774a	1	1	ulan.nusupbekov	u.nusupbekov@gqgroup.kz	$2a$06$A02nYvHMMo7F5JRrO/j8DO0hM0/iryEgunQCgCMRvdUbAA1fO8L2.	editor	t	2025-08-20 09:50:56.582585+00
c17ba46f-b4b0-473c-ac93-cb10cfed0f7e	1	1	akmaral.alibekova	gq-contract-dcc@gqgroup.kz	$2a$06$DnD8V9QKVwqcMaAIpfaEPOMhhKNbm9uvfPKlkuXSKqQOBG/fyXMKG	editor	t	2025-08-20 09:50:56.582585+00
1e37e40d-83fe-4a40-969d-d167cbb3dc35	1	1	gulzhan.esetova	g.yessetova@gqgroup.kz	$2a$06$UkPIf0oW1qQ3kd1aAXwEYugHJ/CLlVaBKaIlCplNT1ybsn09VzED.	editor	t	2025-08-20 09:50:56.582585+00
41ce2e30-8d54-4e8c-9eab-1752b8b08e36	1	1	zhamilya.sagynysheva	gq-contract-admin@gqgroup.kz	$2a$06$nwa6vKzBDianqDZ8rQOAWeL4Q4chK37yjo/Ojie0y9Or7AKmkg5ee	editor	t	2025-08-20 09:50:56.582585+00
6e867ad1-fb23-4447-b455-cf9be49e56a1	1	1	ainur.gubaydullaeva	a.gubaydullaeva@gqgroup.kz	$2a$06$.1fYxjK/EILPRxa17Bj20eS.If4Y.5fYCN48gYH9gb4pxvzxthdDK	editor	t	2025-08-20 09:50:56.582585+00
78f263d3-7976-4b25-a28e-17f39c313b24	1	1	kuanyshbay.kopbayev	k.kopbayev@gqgroup.kz	$2a$06$kmPlgkAa1ZPi6cM6/qJ3meyfa5DuJkAMEm0EpLYcUjqQHTbu5.e2y	editor	t	2025-08-20 09:50:56.582585+00
a90fbe3c-c6d0-475e-b35b-613e022bfa11	1	1	elaman.musin	e.musin@gqgroup.kz	$2a$06$uLRcgaZ6Zbt4tkv2/cLBH.wUan8lcBh4Z0N6JpjurSi59UrP2xE5O	editor	t	2025-08-20 09:50:56.582585+00
c6737eaf-35a2-481c-8ee8-751982a40c5c	1	1	asel.saylaubekova	a.saylaubekova@gqgroup.kz	$2a$06$Ev2LdqcpOf9hoczsr9CZxefwVn2KVO.uNqa8HGAKEv873MrCNAW9W	editor	t	2025-08-20 09:50:56.582585+00
e057eb0f-8763-4f3e-a22b-2a2a9b636ec2	1	1	erkegali.moldagaliyev	y.moldagaliyev@gqgroup.kz	$2a$06$CaCXKg8cSUg0Wq8veGCOxO99Q2byIK68rjoLYJA8F9saEH005D.RO	editor	t	2025-08-20 09:50:56.582585+00
d318dee2-cfc8-4778-a79d-ffbb6e8eade0	1	1	kanat.abakan	k.abakan@gqgroup.kz	$2a$06$yeFpz9P7sTLl.x/qiHRjoOuBADob6Ri0lLRHQnL4dtLtFIIV0Wvoq	editor	t	2025-08-20 09:50:56.582585+00
19e927ed-e1b0-4805-aac9-4178052db74f	1	1	galymzhan.khaimzhan	h.galymzhan@gqgroup.kz	$2a$06$S9NYga2RZ3s/ke3excCp5upMemJH/6VT3XFBD.xo10qV1LyPTWFRK	editor	t	2025-08-20 09:50:56.582585+00
08251138-1569-4f18-994a-0814859c83a1	1	1	aidos.omarov	a.omarov@gqgroup.kz	$2a$06$Gw.2FQu3mEcGq4XGTepOOew/LKztaxNtD8dJh4B69idfUoZgfVxjy	editor	t	2025-08-20 09:50:56.582585+00
bae8ba5a-ad56-4b54-bf39-b84a3b82f45b	1	1	marat.smagulov	m.smagulov@gqgroup.kz	$2a$06$uaJbSmqou3o4Qvrdf1A6nO9Ww32Ria6CcPoWEEEvPkq5Obx2bOJj2	editor	t	2025-08-20 09:50:56.582585+00
9698b7ca-3e83-4ff5-8400-87fb4d0ebfea	1	1	kuanysh.tanatarov	k.tanatarov@gqgroup.kz	$2a$06$9mmTOFJX0nJibGyTShTApOfbFKlJuw6/nFQAclyoVyK705voHDUoy	editor	t	2025-08-20 09:50:56.582585+00
c5e2bb4b-dcbf-4f80-849e-aeb5a876d2c8	1	1	alikhan.amantayev	a.amantayev@gqgroup.kz	$2a$06$AOaR8DZ8.JUvzsYjrvi0Tuht3PwKtIAGu9eAcBnBZUo6AeeWx8pJK	editor	t	2025-08-20 09:50:56.582585+00
23e87a76-a2e3-4d3d-8d4f-60841f4661ce	1	1	veronika.penkova	v.penkova@gqgroup.kz	$2a$06$birG7nwfgJFIKeVB6Kootu2klAk1V5rJu7zM73pvZ3jA2pbr/MZlm	editor	t	2025-08-20 09:50:56.582585+00
79bf1435-c131-498d-9598-44720456cf08	1	1	temirlan.edenbaev	t.edenbaev@gqgroup.kz	$2a$06$DTvwd9rG5SfGo1FZd/Cvw.VMun4DYCnyBb5EfQfc0oSMV2dWWn6Wa	editor	t	2025-08-20 09:50:56.582585+00
651d3760-e28c-4a91-9996-423d88b33e4c	1	1	gq.industrial	gq-industrial@gqgroup.kz	$2a$06$tcYb2wsKGBILDiL6rxRvIuuD3kAMmCDrIU3jVgvH8e6VTZ8O8.gzO	editor	t	2025-09-04 13:34:15.163942+00
6bcf14c9-0e8a-490d-92f6-dc1f15f26e31	1	1	teh.otdel.cc	teh-otdel-cc@gqgroup.kz	$2a$06$DETnxtFcME.fLbC7ruiyuulPWXLOGAVpb7isQDyWuYDqmJzGllDzy	editor	t	2025-09-04 13:34:15.163942+00
2e46fed2-af52-4290-81c5-10e846b0d133	1	1	td.dostyk	TD-Dostyk@gqgroup.kz	$2a$06$YhGiz.6TNewTGBxrvK6f4Ootb0oLk.ZVjhUcpjRXRlutN3NgcYCAS	editor	t	2025-09-04 13:34:15.163942+00
58b15079-d482-4fb3-86ef-242c870b19b8	1	1	gqsystem.almaty	gqsystem-almaty@gqgroup.kz	$2a$06$WrKXlx7Jc4.e6H2KFM3KH.uhn.1ISXVPcaqLJkGRnL5fEK2HDTZua	editor	t	2025-09-04 13:34:15.163942+00
d7fabf93-ffd3-4ce1-9e33-eb3e1ee6b28d	1	1	gqsystem.ug	gqsystem-ug@gqgroup.kz	$2a$06$Cqbdvcr8vhUYx3SCIjkN1.kVIUlpaqxZ064kMr07J98coMPuBl.HW	editor	t	2025-09-04 13:34:15.163942+00
8747b6e3-d058-4e25-a389-4ff7a5f76d19	1	1	gq.construction	gq-construction@gqgroup.kz	$2a$06$kZ6C9CjwPrAFJsKJ/fG3s.bJdJ1ENc18ut11GJZG9eupRIIFssFuG	editor	t	2025-09-04 13:34:15.163942+00
1f4e2ad4-9d93-49c7-924b-82d55ccad67d	1	1	madi	msaduakasea@gmail.com	$2a$06$XrBkhAZA9sNwI8tzmRG//uZyT726oi6kLuWrOj5QWbHDa9SNE7Vsi	editor	t	2025-09-04 13:35:43.874692+00
\.


--
-- Name: departments_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.departments_id_seq', 1, true);


--
-- Name: document_tags_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.document_tags_id_seq', 1, false);


--
-- Name: document_versions_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.document_versions_id_seq', 1, false);


--
-- Name: documents_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.documents_id_seq', 4062, true);


--
-- Name: permissions_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.permissions_id_seq', 1, false);


--
-- Name: shared_documents_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.shared_documents_id_seq', 1, false);


--
-- Name: tags_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.tags_id_seq', 1, false);


--
-- Name: tenants_id_seq; Type: SEQUENCE SET; Schema: public; Owner: postgres
--

SELECT pg_catalog.setval('public.tenants_id_seq', 1, false);


--
-- Name: departments departments_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.departments
    ADD CONSTRAINT departments_pkey PRIMARY KEY (id);


--
-- Name: document_tags document_tags_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.document_tags
    ADD CONSTRAINT document_tags_pkey PRIMARY KEY (id);


--
-- Name: document_versions document_versions_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.document_versions
    ADD CONSTRAINT document_versions_pkey PRIMARY KEY (id);


--
-- Name: documents documents_document_number_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.documents
    ADD CONSTRAINT documents_document_number_key UNIQUE (document_number);


--
-- Name: documents documents_parent_name_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.documents
    ADD CONSTRAINT documents_parent_name_key UNIQUE (parent_id, name);


--
-- Name: documents documents_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.documents
    ADD CONSTRAINT documents_pkey PRIMARY KEY (id);


--
-- Name: notify notify_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.notify
    ADD CONSTRAINT notify_pkey PRIMARY KEY (id);


--
-- Name: permissions permissions_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.permissions
    ADD CONSTRAINT permissions_pkey PRIMARY KEY (id);


--
-- Name: shared_documents shared_documents_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.shared_documents
    ADD CONSTRAINT shared_documents_pkey PRIMARY KEY (id);


--
-- Name: shared_documents shared_documents_token_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.shared_documents
    ADD CONSTRAINT shared_documents_token_key UNIQUE (token);


--
-- Name: tags tags_name_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.tags
    ADD CONSTRAINT tags_name_key UNIQUE (name);


--
-- Name: tags tags_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.tags
    ADD CONSTRAINT tags_pkey PRIMARY KEY (id);


--
-- Name: tenants tenants_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.tenants
    ADD CONSTRAINT tenants_pkey PRIMARY KEY (id);


--
-- Name: document_tags uq_doc_tag; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.document_tags
    ADD CONSTRAINT uq_doc_tag UNIQUE (document_id, tag_id);


--
-- Name: document_versions uq_doc_version; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.document_versions
    ADD CONSTRAINT uq_doc_version UNIQUE (document_id, version_number);


--
-- Name: documents uq_title_parent; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.documents
    ADD CONSTRAINT uq_title_parent UNIQUE (title, parent_id);


--
-- Name: users users_email_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_email_key UNIQUE (email);


--
-- Name: users users_pkey; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_pkey PRIMARY KEY (id);


--
-- Name: users users_username_key; Type: CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_username_key UNIQUE (username);


--
-- Name: ix_notify_id; Type: INDEX; Schema: public; Owner: postgres
--

CREATE INDEX ix_notify_id ON public.notify USING btree (id);


--
-- Name: departments departments_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.departments
    ADD CONSTRAINT departments_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id);


--
-- Name: document_tags document_tags_document_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.document_tags
    ADD CONSTRAINT document_tags_document_id_fkey FOREIGN KEY (document_id) REFERENCES public.documents(id);


--
-- Name: document_tags document_tags_tag_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.document_tags
    ADD CONSTRAINT document_tags_tag_id_fkey FOREIGN KEY (tag_id) REFERENCES public.tags(id);


--
-- Name: document_versions document_versions_document_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.document_versions
    ADD CONSTRAINT document_versions_document_id_fkey FOREIGN KEY (document_id) REFERENCES public.documents(id);


--
-- Name: documents documents_department_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.documents
    ADD CONSTRAINT documents_department_id_fkey FOREIGN KEY (department_id) REFERENCES public.departments(id);


--
-- Name: documents documents_owner_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.documents
    ADD CONSTRAINT documents_owner_id_fkey FOREIGN KEY (owner_id) REFERENCES public.users(id);


--
-- Name: documents documents_parent_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.documents
    ADD CONSTRAINT documents_parent_id_fkey FOREIGN KEY (parent_id) REFERENCES public.documents(id);


--
-- Name: documents documents_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.documents
    ADD CONSTRAINT documents_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id);


--
-- Name: notify notify_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.notify
    ADD CONSTRAINT notify_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: permissions permissions_document_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.permissions
    ADD CONSTRAINT permissions_document_id_fkey FOREIGN KEY (document_id) REFERENCES public.documents(id);


--
-- Name: permissions permissions_user_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.permissions
    ADD CONSTRAINT permissions_user_id_fkey FOREIGN KEY (user_id) REFERENCES public.users(id);


--
-- Name: shared_documents shared_documents_document_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.shared_documents
    ADD CONSTRAINT shared_documents_document_id_fkey FOREIGN KEY (document_id) REFERENCES public.documents(id);


--
-- Name: shared_documents shared_documents_shared_by_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.shared_documents
    ADD CONSTRAINT shared_documents_shared_by_fkey FOREIGN KEY (shared_by) REFERENCES public.users(id);


--
-- Name: shared_documents shared_documents_shared_with_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.shared_documents
    ADD CONSTRAINT shared_documents_shared_with_fkey FOREIGN KEY (shared_with) REFERENCES public.users(id);


--
-- Name: users users_department_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_department_id_fkey FOREIGN KEY (department_id) REFERENCES public.departments(id);


--
-- Name: users users_tenant_id_fkey; Type: FK CONSTRAINT; Schema: public; Owner: postgres
--

ALTER TABLE ONLY public.users
    ADD CONSTRAINT users_tenant_id_fkey FOREIGN KEY (tenant_id) REFERENCES public.tenants(id);


--
-- PostgreSQL database dump complete
--

