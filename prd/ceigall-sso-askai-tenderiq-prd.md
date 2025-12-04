**RoadVision AI** 

## **Ceigall AI Platform \- Comprehensive AI Solutions Suite**

## **Product Overview**

The Ceigall AI Platform is a comprehensive AI solution designed to streamline and automate day-to-day operations across multiple departments at Ceigall India Pvt Limited. The platform integrates advanced artificial intelligence capabilities with robust data management, providing a unified interface for employees across Tender & Bidding, Contracts & Legal, HR, Procurement, Store, Finance & Billing, and other departments.

## **Product Vision**

To create a centralized, intelligent ecosystem that empowers Ceigall employees to work more efficiently, make data-driven decisions, and access departmental resources seamlessly through AI-powered automation and insights.

## **Business Objectives**

* Reduce operational overhead by 40% through automation and AI-driven workflows​  
* Improve cross-departmental collaboration and information accessibility​  
* Enhance decision-making speed with real-time AI-powered insights​  
* Ensure data security and compliance with role-based access control​  
* Increase employee productivity by eliminating redundant manual tasks


1. ## **Single Sign-On (SSO) Module**

## **1.1 Module Overview**

The SSO module serves as the centralized authentication gateway for the Ceigall AI Platform, enabling users to register with their Ceigall email, access modules based on their department and assigned permissions, and manage their profile through a unified interface.

## **1.2 User Roles & Access Levels**

## **1.2.1 Role Hierarchy**

Super Admin

* Full system access and configuration​  
* User management across all departments​  
* Module access control for all employees​  
* System settings and security management​  
* Analytics and audit log access​

Department Admin

* User management within their department​  
* Module access requests for department members​  
* Department-specific analytics viewing​

Employee

* Access to assigned modules based on department and admin approval​  
* Profile management​  
* Standard features within permitted modules​

## **1.3 Core Features**

## **1.3.1 User Registration**

Registration Process  
User Story: As a Ceigall employee, I want to register using my company email so that I can access the AI platform.​

Requirements:

* Registration restricted to @ceigall.com email domain only​  
* Email verification via OTP sent to Ceigall email address​  
* OTP validity: 10 minutes​

Registration Form Fields:

Personal Information

* Full Name (mandatory)​  
* Employee ID (mandatory, validated against HR database)​  
* Ceigall Email Address (mandatory, auto-verified)​  
* Mobile Number (mandatory, 10-digit Indian format)​  
* Designation/Position (mandatory)​  
* Profile Picture (optional, auto-cropped to square)​

Department Selection

* Department dropdown (mandatory, single selection/multiple selection?):​  
  * Tender & Bidding  
  * Contracts & Legal  
  * Human Resources  
  * Procurement  
  * Store Management  
  * Finance & Billing  
  * Project Management  
  * Administration  
  * IT & Systems  
  * Other

Password Creation

* Password requirements:​  
  * Minimum 12 characters  
  * At least one uppercase letter  
  * At least one lowercase letter  
  * At least one number  
  * At least one special character (@, \#, $, %, &, \*, \!)  
* Password strength indicator (weak, medium, strong)​  
* Confirm password field with real-time matching validation​

Registration Workflow:

1. User enters Ceigall email address  
2. System validates email domain (@ceigall.com)  
3. OTP sent to email address  
4. User enters OTP for verification  
5. User completes registration form with personal details and department selection  
6. User creates password  
7. System creates account with "Pending Approval" status  
8. Admin receives notification for account activation  
9. Upon admin approval, user receives activation email  
10. User can now log in with default module access (Dashboard, DMSIQ, Ask CeigallAI)​

Registration Success:

* Welcome email sent with platform introduction​  
* Quick start guide attachment​  
* Default access to Dashboard, DMSIQ and Ask CeigallAI modules​  
* Account status: Active​

## **1.3.2 User Authentication**

Login Process  
User Story: As a registered employee, I want to log in securely using my email and password so that I can access the platform.​

Requirements:

* Login credentials:​  
  * Ceigall email address (username)  
  * Password (created during registration)  
* "Remember me" option for trusted devices (30-day validity)​  
* Automatic session timeout after 30 minutes of inactivity​  
* Maximum 3 concurrent sessions per user​

Login Security:

* Progressive account lockout:​  
  * After 3 failed attempts: 5-minute lockout  
  * After 5 failed attempts: Account locked, admin intervention required  
* CAPTCHA appears after 2 failed login attempts​  
* Login attempt logging with IP address and timestamp​  
* Suspicious activity detection (unusual location, multiple failures)​  
* Email notification for login from new device​

Password Reset:

* "Forgot Password" link on login page​  
* Email-based password reset workflow:​  
  1. User enters registered email  
  2. System sends password reset link (valid for 1 hour)  
  3. User clicks link and creates new password  
  4. System validates password against policy  
  5. Confirmation email sent upon successful reset  
* Cannot reuse last 5 passwords​  
* Password expiry: 90 days with 7-day advance notification​

Session Management:

* Encrypted session tokens using JWT​  
* Session invalidation upon password change​  
* "Logout from all devices" option in user profile​  
* Automatic logout on browser close (if "Remember me" not selected)​

## **1.3.3 Post-Login Dashboard**

**Dashboard Overview**  
User Story: As a logged-in user, I want to see a personalized dashboard that shows relevant modules and system insights.​

**Dashboard Header:**

* Ceigall logo (left)​  
* Global search bar (search across all accessible modules)​  
* Notification bell icon with unread count​  
* User profile dropdown (right):​  
  * User name and designation  
  * Profile picture  
  * My Profile option  
  * Settings option  
  * Logout option

Navigation Sidebar (Left Panel):

AI Modules Section (Always visible icons)​

* Dashboard (home icon) \- visible to all​  
* Ask CeigallAI (chat icon) \- visible to all​  
* DesignIQ (design icon) \- department-based access  
* TenderIQ (document icon) \- Tender & Bidding department only​  
* DMSIQ (folder icon) \- visible to all​  
* LegalIQ (legal icon) \- Contracts & Legal department only​


Module Visibility Logic:

* Universal Access (All Users):​  
  * Dashboard  
  * Ask CeigallAI  
  * DMSIQ  
* Department-Based Access:​  
  * TenderIQ: Tender & Bidding department members only  
  * LegalIQ (HRIQ, ProcurementIQ, etc.): Respective department members only  
  * Additional modules visible only if admin grants access  
* Admin-Controlled Access:​  
  * Admins can grant cross-departmental module access  
  * Temporary access can be granted for specific projects  
  * Access changes take effect immediately upon admin approval

Dashboard Main Content Area:

System Summary Cards (Top Row \- 3 cards)​

1. Active Users Card  
   * Icon: User group icon  
   * Metric: Total number of active employees using the system  
   * Example: "156 Active Users"  
   * Trend indicator: Arrow showing increase/decrease from previous period  
2. AI Queries Today Card  
   * Icon: Message/chat icon  
   * Metric: Total queries processed in Ask CeigallAI module today  
   * Example: "342 AI Queries Today"  
   * Trend indicator: Percentage change from yesterday  
3. Tenders Analyzed Card (Visible to Tender & Bidding dept)​  
   * Icon: Document analysis icon  
   * Metric: Total tenders analyzed in TenderIQ module  
   * Example: "28 Tenders Analyzed"  
   * Time filter: This month/quarter/year

Quick Actions Section (4 cards in 2x2 grid)​

1. Start AI Conversation  
   * Icon: Chat bubble  
   * Description: "Chat with CeigallAI for instant infrastructure insights"  
   * Click action: Opens Ask CeigallAI module  
2. Analyze Design  
   * Icon: Design/palette icon  
   * Description: "Upload and get AI feedback on your infrastructure designs"  
   * Click action: Opens DesignIQ module  
   * Visibility: Based on access permissions  
3. Review Tender (Department-specific)​  
   * Icon: Document icon  
   * Description: "Get comprehensive tender analysis and summaries"  
   * Click action: Opens TenderIQ module  
   * Visibility: Tender & Bidding department only  
4. Query Documents  
   * Icon: Search/folder icon  
   * Description: "Search your document management system with AI"  
   * Click action: Opens DMSIQ module

Recent Activity Section (Bottom)​

* Title: "Recent Activity"  
* Subtitle: "Your latest AI interactions and uploads"  
* Activity feed showing:  
  * Activity type icon (document, chat, analysis)  
  * Activity title  
  * Timestamp (e.g., "2 hours ago", "Yesterday")  
  * Status indicator (Complete, In Progress)  
* Show last 5-10 activities  
* "View All" link to see complete history

Dashboard Personalization:

* Dashboard content adapts based on user's department​  
* Quick action cards show only accessible modules​  
* Recent activity filtered to user's own actions​  
* System summary shows relevant metrics for user's role​

## **1.3.4 Admin Dashboard & User Management**

Admin Dashboard  
User Story: As an admin, I want a comprehensive dashboard to manage users and their module access so that I can ensure proper security and permissions.​

Admin Panel Access:

* Accessible via admin-specific menu item​  
* Role verification before allowing access​  
* Separate admin interface from regular dashboard​

User Management Interface:

User List View  
Requirements:

* Tabular display of all registered users​  
* Columns displayed:  
  * Profile picture thumbnail  
  * Full name  
  * Employee ID  
  * Email address  
  * Department  
  * Designation  
  * Account status (Active, Inactive, Locked, Pending Approval)  
  * Last login (date and time)  
  * Actions (Edit, View Details, Manage Access)

Filtering & Search:

* Search by name, email, or employee ID​  
* Filter by department (dropdown)​  
* Filter by account status (dropdown)​  
* Filter by module access​  
* Sort by any column (ascending/descending)​  
* Bulk selection for batch operations​

User Account Management:

Activate/Deactivate Users

* Toggle switch for quick activation/deactivation​  
* Bulk activate/deactivate selected users​  
* Deactivation confirmation dialog​  
* Email notification to user upon status change​

Module Access Management  
User Story: As an admin, I want to control which modules each employee can access so that permissions are properly enforced.​

Access Control Interface:

* "Manage Access" button for each user​  
* Modal popup showing module access matrix​  
* Module list with toggle switches:  
  * Ask CeigallAI (default ON, cannot be disabled)​  
  * DMSIQ (default ON, cannot be disabled)​  
  * TenderIQ (toggle, default based on department)  
  * LegalIQ (toggle, default based on department)  
  * HRIQ (toggle, default based on department)  
  * ProcurementIQ (toggle, default based on department)  
  * StoreIQ (toggle, default based on department)  
  * FinanceIQ (toggle, default based on department)  
  * ProjectIQ (toggle, default based on department)

Access Grant Workflow:

1. Admin selects user  
2. Clicks "Manage Access" button  
3. Modal shows current module access status  
4. Admin toggles modules ON/OFF  
5. Optional: Add access validity period (start and end date)  
6. Optional: Add access reason/justification  
7. Click "Save Changes"  
8. System updates user permissions immediately  
9. User receives email notification of access changes  
10. Access change logged in audit trail​

Department-Based Default Access:

* New users automatically get access to universal modules​  
* Department-specific module access auto-assigned based on department selection​  
* Admin can override default access settings​

Bulk Module Access Assignment:

* Select multiple users via checkboxes​  
* "Bulk Manage Access" button​  
* Grant or revoke access to specific modules for all selected users​  
* Useful for project teams or temporary access needs​

User Profile Management (Admin):

View User Details:

* Complete user information display​  
* Registration date and registration IP address​  
* Account activation date  
* Last password change date  
* Module access history  
* Login history (last 20 logins)​  
* Activity summary (documents uploaded, queries made)​

Edit User Information:

* Update name, employee ID, designation​  
* Change department (triggers module access review)​  
* Update mobile number​  
* Reset user password (system generates temporary password)​  
* Unlock locked accounts​

Account Actions:

* Force password reset on next login​  
* Terminate all active sessions​  
* Send welcome email again​  
* View audit trail for specific user​  
* Permanently delete user (with data retention policy compliance)​

## **1.3.5 User Self-Service Features**

My Profile Section  
User Story: As an employee, I want to manage my profile information so that my details are current.​

Profile Information Display:

* Profile picture with upload/change option​  
* Full name  
* Employee ID (read-only)  
* Ceigall email (read-only)  
* Mobile number (editable)  
* Department (read-only, contact admin to change)  
* Designation (read-only, contact admin to change)  
* Account created date  
* Last password change date

Editable Fields:

* Profile picture upload​  
* Mobile number with OTP verification​  
* Password change (requires current password)​

Password Change:

* Current password field​  
* New password field with strength indicator​  
* Confirm new password field​  
* Password requirements reminder​  
* Submit button  
* Success confirmation with email notification​

My Module Access:

* Display list of modules user has access to​  
* Module name with icon  
* Access granted date  
* Access type (Default, Admin-granted)  
* "Request Additional Access" button (submits request to admin)​

Login History:

* Display last 10 login sessions​  
* Date and time  
* Device type (Desktop, Mobile)  
* Browser information  
* IP address  
* Location (city, if available)  
* Status (Successful, Failed)

Active Sessions:

* List of currently active sessions​  
* Device information  
* Login time  
* Last activity time  
* "Logout" button for each session​  
* "Logout All Sessions" button​

Notification Preferences:

* Email notifications toggle​  
* SMS notifications toggle​  
* In-app notifications toggle​  
* Notification types configuration:  
  * Security alerts (always enabled)  
  * Module updates  
  * System announcements  
  * Activity reminders  
  * Weekly summary

## **1.3.6 Security Features**

Account Security  
Requirements:

* Ceigall email domain restriction (@ceigall.com only)​  
* Strong password policy enforcement​  
* Account lockout after failed login attempts​  
* CAPTCHA integration for brute force prevention​  
* Session encryption using JWT tokens​  
* Secure password storage with bcrypt hashing​  
* Password expiry every 90 days​

Data Protection  
Requirements:

* TLS 1.3 encryption for all data transmission​  
* AES-256 encryption for sensitive data at rest​  
* Secure session management with HttpOnly cookies​  
* No plain-text password storage or logging​  
* Session invalidation on password change​

Access Control  
Requirements:

* Role-based access control (RBAC)​  
* Department-based default permissions​  
* Admin approval required for module access​  
* Immediate access revocation capability​  
* Audit trail for all access changes​

Monitoring & Alerts  
Requirements:

* Real-time login monitoring​  
* Failed login attempt tracking​  
* Unusual activity detection:​  
  * Login from new device  
  * Login from unusual location  
  * Multiple concurrent sessions  
  * Multiple failed password attempts  
* Automated security alerts to admins​  
* Email notifications to users for security events​

## **1.3.7 Audit & Compliance**

Audit Trail  
Requirements:

* Comprehensive logging of all SSO activities:​  
  * User registration and activation  
  * Login and logout events  
  * Password changes and resets  
  * Profile updates  
  * Module access changes  
  * Failed authentication attempts  
  * Session terminations  
  * Admin actions on user accounts

Audit Log Details:

* Timestamp (date and time with milliseconds)​  
* User identifier (name and email)​  
* Action performed​  
* IP address​  
* Device and browser information​  
* Status (Success, Failed, Partial)​  
* Additional context/details​

Compliance Reporting:

* User access reports (who has access to what)​  
* Login activity reports (successful and failed)​  
* Password compliance reports (expired, weak passwords)​  
* Account status reports (active, inactive, locked)​  
* Module access audit reports​  
* Security incident reports​

Data Retention:

* Audit logs retention: 7 years minimum​  
* Tamper-proof audit trail with cryptographic signing​  
* Compliance with Indian data protection regulations​  
* Export capability for audit reports (PDF, CSV, Excel)​

## **1.3.8 Integration Capabilities**

HR System Integration  
Requirements:

* Employee ID validation against HR database​  
* Automatic department information sync​  
* Employee status updates (active, resigned, transferred)​  
* New joinee automatic account creation notification​

Email System Integration  
Requirements:

* SMTP integration for transactional emails​  
* Email templates for:  
  * Registration verification OTP  
  * Account activation confirmation  
  * Password reset links  
  * Security alerts  
  * Module access notifications  
  * Welcome emails

Directory Service Integration  
Requirements:

* Optional Active Directory integration for enterprise SSO​  
* LDAP synchronization for user information​  
* Group membership sync for department-based access​

API Endpoints  
Requirements:

* RESTful API for authentication services​  
* JWT token generation and validation​  
* User profile API endpoints​  
* Module access verification API​  
* Session management API​  
* API documentation with authentication examples​

---

## **1.4 User Flows**

## **1.4.1 New User Registration Flow**

1. User navigates to registration page  
2. Enters Ceigall email address (@ceigall.com)  
3. Receives OTP via email  
4. Enters OTP for verification  
5. Completes registration form (name, employee ID, mobile, department, designation)  
6. Uploads profile picture (optional)  
7. Creates password meeting security requirements  
8. Submits registration  
9. Receives "Registration Pending Approval" message  
10. Admin reviews and approves account  
11. User receives activation email  
12. User logs in with email and password  
13. Lands on dashboard with default access to DMSIQ and Ask CeigallAI

## **1.4.2 User Login Flow**

1. User navigates to login page  
2. Enters Ceigall email and password  
3. (If new device) Completes CAPTCHA  
4. System validates credentials  
5. Session created with JWT token  
6. User redirected to dashboard  
7. Dashboard displays based on user's department and module access  
8. User sees universal modules (Dashboard, Ask CeigallAI, DMSIQ)  
9. User sees department-specific modules (TenderIQ for Tender dept, etc.)  
10. User sees admin-granted additional modules (if any)

## **1.4.3 Admin Module Access Grant Flow**

1. Admin logs into admin dashboard  
2. Navigates to User Management section  
3. Searches/filters for specific user  
4. Clicks "Manage Access" button  
5. Views current module access status  
6. Toggles ON desired modules  
7. Sets access validity period (optional)  
8. Adds access justification (optional)  
9. Saves changes  
10. System updates permissions immediately  
11. User receives email notification  
12. User logs out and logs back in  
13. User sees newly granted modules in sidebar

## **1.4.4 Password Reset Flow**

1. User clicks "Forgot Password" on login page  
2. Enters registered Ceigall email  
3. Receives password reset link via email (valid 1 hour)  
4. Clicks link in email  
5. Redirected to password reset page  
6. Enters new password meeting requirements  
7. Confirms new password  
8. Submits password change  
9. Receives confirmation email  
10. Redirected to login page  
11. Logs in with new password

---

## **1.5 Technical Specifications**

## **1.5.1 Authentication Protocol**

* JWT (JSON Web Token) based authentication​  
* Token expiry: 24 hours for active sessions​  
* Refresh token mechanism for extended sessions​  
* Token encryption and signing​

## **1.5.2 Database Schema**

Users Table:

* user\_id (Primary Key, UUID)  
* employee\_id (Unique, String)  
* full\_name (String)  
* email (Unique, String, @ceigall.com)  
* mobile\_number (String)  
* department (String)  
* designation (String)  
* password\_hash (String, bcrypt)  
* profile\_picture\_url (String)  
* account\_status (Enum: Active, Inactive, Locked, Pending)  
* created\_at (Timestamp)  
* updated\_at (Timestamp)  
* last\_login (Timestamp)  
* last\_password\_change (Timestamp)  
* failed\_login\_attempts (Integer)  
* password\_expiry\_date (Date)

Module\_Access Table:

* access\_id (Primary Key, UUID)  
* user\_id (Foreign Key)  
* module\_name (String)  
* access\_type (Enum: Default, Admin-Granted)  
* granted\_by (Foreign Key to Users, nullable)  
* granted\_at (Timestamp)  
* valid\_from (Date, nullable)  
* valid\_until (Date, nullable)  
* access\_reason (Text, nullable)  
* is\_active (Boolean)

Login\_History Table:

* login\_id (Primary Key, UUID)  
* user\_id (Foreign Key)  
* login\_timestamp (Timestamp)  
* ip\_address (String)  
* device\_type (String)  
* browser (String)  
* location (String, nullable)  
* status (Enum: Success, Failed)  
* failure\_reason (String, nullable)

Audit\_Logs Table:

* audit\_id (Primary Key, UUID)  
* user\_id (Foreign Key, nullable)  
* action\_type (String)  
* action\_description (Text)  
* timestamp (Timestamp)  
* ip\_address (String)  
* device\_info (JSON)  
* status (Enum: Success, Failed, Partial)  
* additional\_data (JSON)

## **1.5.3 API Endpoints**

Authentication APIs:

* POST /api/auth/register \- User registration  
* POST /api/auth/verify-otp \- Email OTP verification  
* POST /api/auth/login \- User login  
* POST /api/auth/logout \- User logout  
* POST /api/auth/refresh-token \- Refresh JWT token  
* POST /api/auth/forgot-password \- Initiate password reset  
* POST /api/auth/reset-password \- Complete password reset  
* GET /api/auth/validate-token \- Validate JWT token

User Management APIs (Admin):

* GET /api/admin/users \- List all users with filters  
* GET /api/admin/users/:userId \- Get user details  
* PUT /api/admin/users/:userId \- Update user information  
* POST /api/admin/users/:userId/activate \- Activate user account  
* POST /api/admin/users/:userId/deactivate \- Deactivate user account  
* GET /api/admin/users/:userId/access \- Get user's module access  
* PUT /api/admin/users/:userId/access \- Update user's module access  
* POST /api/admin/users/:userId/reset-password \- Admin reset user password  
* POST /api/admin/users/:userId/unlock \- Unlock user account  
* DELETE /api/admin/users/:userId/sessions \- Terminate user sessions

User Profile APIs:

* GET /api/users/profile \- Get current user profile  
* PUT /api/users/profile \- Update profile information  
* POST /api/users/profile/picture \- Upload profile picture  
* PUT /api/users/change-password \- Change password  
* GET /api/users/module-access \- Get user's module access  
* GET /api/users/login-history \- Get login history  
* GET /api/users/active-sessions \- Get active sessions  
* DELETE /api/users/sessions/:sessionId \- Logout specific session

Dashboard APIs:

* GET /api/dashboard/summary \- Get dashboard summary stats  
* GET /api/dashboard/recent-activity \- Get recent activity feed

## **1.5.4 Security Specifications**

Password Policy:

* Minimum length: 12 characters  
* Character requirements: uppercase, lowercase, numbers, special characters  
* Password history: Cannot reuse last 5 passwords  
* Password expiry: 90 days  
* Password strength validation on client and server side

Session Security:

* JWT token signed with HS256 algorithm  
* Token includes: user\_id, email, role, department, module\_access, issued\_at, expires\_at  
* Session timeout: 30 minutes of inactivity  
* Maximum concurrent sessions: 3 per user  
* Secure, HttpOnly cookies for token storage

Account Lockout:

* Threshold: 5 failed login attempts  
* Lockout duration: Permanent (admin unlock required)  
* CAPTCHA trigger: After 2 failed attempts  
* Lockout notification: Email to user and admin

## **2\. Ask Ceigall AI**

## **2.1 Module Overview**

Ask CeigallAI is an intelligent conversational AI assistant that provides instant answers, document analysis, and insights to Ceigall employees across all departments. The module features a chat-based interface with multi-document upload capabilities, seamless integration with DMSIQ for accessing stored documents, and context-aware responses based on company knowledge.​

Module Access: Universal \- Available to all registered users

Key Value Proposition:

* Reduce document analysis time by 50%​  
* Instant answers to company policies, procedures, and project information​  
* Multi-document reasoning and comparison capabilities​  
* Department-specific intelligent assistance​

---

## **2.2 User Interface Design**

## **2.2.1 Layout Structure**

Left Sidebar (Chat History)

* Dark/Light theme toggle (top-left)  
* Search conversations button  
* "+ New Chat" button (prominent, full width)  
* Conversation history list showing:  
  * Chat title (auto-generated or user-named)  
  * Timestamp and message count  
  * Grouped by date (Today, Yesterday, Last 7 days, etc.)  
* Hover actions: Rename, Delete, Archive

Main Chat Area (Center)

* Ceigall logo and branding  
* Chat title with edit capability  
* Welcome message: "Chat with AI"  
* Subtitle: "Start a conversation or upload a document to get started"  
* Message thread with AI and user messages  
* Markdown formatting support for responses  
* Real-time typing indicators

Right Sidebar (Documents Panel)

* "Documents" button to toggle panel visibility  
* List of all uploaded/imported documents in current conversation  
* Document preview and management options  
* Source indicator (Uploaded vs. From DMSIQ)

Input Area (Bottom)

* Multi-line text input: "Ask me anything..."  
* "Upload File" button with icon  
* Send button (paper plane icon)  
* Keyboard shortcut hints: "Shift+Enter for new line. Esc to clear"

## **2.2.2 Suggested Prompts**

Initial Chat Screen  
Display 4 suggested prompt cards in 2×2 grid layout when starting a new conversation:

Example Prompts (Tender & Bidding Department):

1. Summarize tender requirements \- "Summarize the key requirements for the latest infrastructure tender"  
2. Check eligibility criteria \- "What are the eligibility criteria for the recent IT services proposal?"  
3. Compare tender deadlines \- "Compare the deadlines for the top 3 construction tenders"  
4. Find renewable energy tenders \- "Find any tenders related to renewable energy in the last month"

Dynamic Behavior:

* Prompts adapt based on user's department  
* HR department sees policy and employee-related prompts  
* Finance department sees budget and financial analysis prompts  
* Prompts update based on recent activity and trending queries

---

## **2.3 Core Features**

## **2.3.1 Conversational AI Interface**

Natural Language Understanding  
User Story: As an employee, I want to ask questions in natural language so that I can get quick answers without learning specific commands.​

Capabilities:

* Natural conversation in English  
* Multi-turn dialogue with context retention across conversation  
* Intent recognition and entity extraction (dates, amounts, names, locations)​  
* Question reformulation and clarification requests when needed  
* Follow-up question handling with conversational memory

Query Types Supported:

* Informational: "What is the EMD requirement for tender ABC123?"  
* Analytical: "Compare the financial terms of the last 3 highway projects"  
* Document-based: "Summarize the technical specifications in this document"​  
* Procedural: "How do I submit a leave application?"  
* Search: "Find all tenders related to bridge construction"  
* Calculation: "Calculate the total cost for 500 units at Rs. 1,250 per unit"  
* Data extraction: "Extract all deadline dates from this tender document"​  
* Reasoning: "Why was our bid rejected for the XYZ project?"​

Response Generation:

* Clear, concise answers in conversational tone  
* Structured responses with bullet points and numbered lists  
* Markdown formatting (bold, italic, headers, tables)  
* Code blocks with syntax highlighting for technical content  
* Inline citations to source documents and knowledge base  
* "I don't know" responses when information unavailable with suggestions for alternatives  
* Streaming responses for real-time feedback

Context Awareness:

* Department-aware responses customized to user's role  
* Conversation history retention within session  
* Reference to previously uploaded documents  
* Project/tender-specific context when applicable

## **2.3.2 Document Upload & Management**

Multi-Document Upload  
User Story: As a user, I want to upload multiple documents simultaneously to analyze them together so that I can extract cross-document insights.​

Upload Interface:

* "Upload File" button in chat input area  
* Drag-and-drop zone anywhere in chat area  
* Multiple file selection support  
* Real-time upload progress indicators  
* Success/failure notifications per file

Supported File Formats:

* Documents: PDF, DOC, DOCX, TXT, RTF, ODT​  
* Spreadsheets: XLS, XLSX, CSV  
* Presentations: PPT, PPTX  
* Images: JPG, PNG, GIF, BMP (with OCR processing)​  
* CAD Files: DWG, DXF (basic support)  
* Archives: ZIP (extracts and processes contents)

Upload Limits:

* Maximum file size per upload: 100 MB  
* Maximum files per conversation: 20 files  
* Total size limit per conversation: 500 MB  
* Automatic virus and malware scanning

Document Processing:

* Automatic text extraction from all document types​  
* OCR (Optical Character Recognition) for scanned documents​  
* Table extraction and structuring​  
* Metadata extraction (title, author, date, page count)  
* Processing status indicators (Processing, Ready, Failed)  
* Estimated processing time for large files  
* Vector embedding generation for semantic search​

## **2.3.3 Documents Panel**

User Story: As a user, I want to view and manage all documents in my conversation so that I can track what context the AI is using.​

Panel Features:

* Click "Documents" button to open right sidebar  
* Visual list of all documents in current conversation  
* Each document shows:  
  * Thumbnail/icon based on file type  
  * Document name (with ellipsis for long names)  
  * File size and upload timestamp  
  * Processing status badge  
  * Page count (for multi-page documents)  
  * Source indicator (Uploaded or From DMSIQ)

Document Actions:

* Preview: In-app document viewer with zoom and navigation  
* Download: Download original file  
* Remove: Remove from conversation context  
* View in DMSIQ: Open source document in DMSIQ (for imported files)  
* Copy reference: Copy document identifier for specific queries

Document Organization:

* Sort by: Name, Date, Size, Type  
* Filter by file type  
* Search documents by name  
* Select multiple documents for bulk actions  
* Clear all documents option

## **2.3.4 DMSIQ Integration**

User Story: As a user, I want to access documents from DMSIQ directly in my chat so that I don't need to download and re-upload files.​

Integration Features:

Import from DMSIQ:

* "Import from DMSIQ" button in upload area  
* Opens DMSIQ document browser in modal window  
* Browse folder structure with tree navigation  
* Search DMSIQ documents with filters  
* Multi-select documents with checkboxes  
* "Add to Chat" button shows selected count  
* Access control: Only shows documents user has permission to view

DMSIQ Browser Interface:

* Modal overlay on chat interface  
* Left panel: Folder tree navigation  
* Right panel: Document grid/list view  
* Top: Search bar with filters (Department, Project, Date range, File type)  
* Document preview on hover  
* Batch import: Up to 50 documents at once  
* Import entire folders for project-related work

Real-Time Sync:

* Notification if DMSIQ document is updated during conversation  
* Option to reload latest version  
* Version history access for imported documents  
* Maintain link to source document in DMSIQ  
* Optional: Auto-save uploaded documents to DMSIQ for future reference

Access Control:

* Respect DMSIQ confidentiality levels and permissions  
* Department-based document filtering  
* Project-based access control  
* Audit trail for document access from chat

## **2.3.5 Document-Based Querying & Analysis**

User Story: As a user, I want to ask specific questions about uploaded documents so that I can quickly extract insights without manual reading.​

Query Capabilities:

Single Document Analysis:

* "Summarize this document"​  
* "What are the key points in document\_name.pdf?"  
* "Extract all dates mentioned in this file"  
* "List the eligibility criteria from the tender document"  
* "What is the EMD amount mentioned?"  
* "Find all financial terms in this contract"  
* "Identify risks mentioned in this agreement"

Cross-Document Analysis:​

* "Compare the deadlines in these three tender documents"  
* "What are the differences between contract A and contract B?"  
* "Summarize common requirements across all uploaded tenders"  
* "Which document has the lowest price quote?"  
* "Create a comparison table of technical specifications from these files"

Deep Reasoning & Analysis:​

* "Analyze the risks mentioned in this contract"  
* "What are the penalty clauses in this agreement?"  
* "Identify missing information in this tender response"  
* "Check compliance with company policies in this document"  
* "Should we pursue this tender based on the requirements?"  
* "What are the pros and cons of these payment terms?"

Data Extraction:​

* "Create a table of all deadlines from these documents"  
* "Extract contact information from these files"  
* "List all technical specifications mentioned"  
* "Generate a comparison matrix from these quotations"  
* "Extract all monetary values and categorize them"

AI Response with Citations:

* Responses include specific page and section references​  
* "Found on page 5, paragraph 3" citations  
* Clickable citations that highlight relevant sections in document viewer  
* Confidence scores for extracted information  
* Option to view source text for verification

## **2.3.6 Knowledge Base Integration**

User Story: As an employee, I want CeigallAI to have access to company information so that I get accurate, context-aware answers about policies and procedures.​

Knowledge Sources:

Company Information:

* Company profile, history, and values  
* Organizational structure and hierarchy  
* Department functions and responsibilities  
* Key personnel directory and contact information  
* Office locations, facilities, and amenities

Policies & Procedures:

* HR policies (leave, attendance, code of conduct, benefits)  
* Procurement processes and approval workflows  
* Financial policies and expense guidelines  
* Safety, security, and compliance guidelines  
* IT policies, helpdesk procedures, and system access

Project & Tender Database:

* Historical tender information and outcomes  
* Past project details, timelines, and learnings  
* Vendor and client information database  
* Standard templates and document formats  
* Technical specifications library  
* Compliance requirements and certifications

Regulatory & Compliance:

* Industry regulations and standards  
* Government procurement rules and guidelines  
* Quality certifications and requirements  
* Legal and contractual obligations  
* Environmental and safety standards

Knowledge Base Management:

* Admin interface to add/update/archive knowledge articles  
* Content approval workflow for quality control  
* Version control for policy documents  
* Periodic knowledge refresh and accuracy validation  
* Analytics on frequently queried topics for gap identification

## **2.3.7 Department-Specific Intelligence**

User Story: As a department member, I want AI to understand my specific work context so that responses are relevant and actionable.​

Tender & Bidding Department:

* Tender document analysis and requirement extraction​  
* Eligibility verification against company profile  
* Compliance checklist generation from RFP  
* Bid preparation guidance and best practices  
* Competitor analysis from historical data  
* Win probability assessment  
* Document gap identification  
* Cost estimation support

Contracts & Legal Department:

* Contract clause extraction and explanation  
* Risk identification in agreements  
* Legal terminology clarification  
* Compliance verification against regulations  
* Contractual obligation extraction and tracking  
* Comparative clause analysis across contracts  
* Amendment impact assessment

Human Resources:

* HR policy clarification and interpretation  
* Leave balance and attendance queries  
* Recruitment process guidance  
* Performance review templates and criteria  
* Employee benefits information  
* Onboarding checklist and procedures

Finance & Billing:

* Financial data queries (with access control)  
* Budget utilization and variance analysis  
* Invoice status and payment tracking  
* Expense policy clarification  
* Tax calculation assistance  
* Financial approval workflow guidance

Procurement:

* Vendor information and performance history  
* Purchase order status tracking  
* Procurement process step-by-step guidance  
* Rate contract queries and applicability  
* Vendor comparison and recommendation

General Queries (All Departments):

* Employee directory search  
* IT helpdesk FAQs and troubleshooting  
* Office facilities and booking information  
* Company events and announcements  
* Travel policy and reimbursement procedures

## **2.3.8 Advanced AI Capabilities**

Reasoning & Analysis  
User Story: As a decision-maker, I want AI to provide insights and recommendations, not just retrieve information.​

Reasoning Capabilities:

* Logical inference from multiple data points  
* Cause-and-effect analysis from documents  
* Pros and cons evaluation for decisions  
* Risk assessment and identification​  
* Scenario analysis ("What if" questions)  
* Recommendation generation with justification

Example Reasoning Queries:

* "Should we bid for this tender based on our current capacity?"  
* "What are the risks of accepting these payment terms?"  
* "Why might our previous bid have been rejected?"  
* "What's the optimal approach to reduce project costs by 10%?"

Mathematical & Financial Calculations:

* Basic arithmetic and complex calculations  
* Financial calculations (EMD, performance guarantee, GST, TDS)  
* Unit conversions (measurements, currency)  
* Percentage and ratio calculations  
* Statistical analysis from uploaded data

Summarization Types:​

* Extractive: Key sentences from original document  
* Abstractive: Rewritten summary in AI's own words  
* Executive summary: High-level overview for management  
* Detailed summary: Section-by-section breakdown  
* Bullet-point summary: Quick takeaways and action items  
* Adjustable length (short: 3-5 sentences, medium: 1 paragraph, detailed: multiple paragraphs)

Multi-Step Problem Solving:

* Break down complex queries into logical steps  
* Show reasoning process transparently  
* Provide intermediate results for validation  
* Allow user to guide and redirect the analysis process

## **2.3.9 Conversation Management**

Chat History & Organization  
User Story: As a user, I want to organize and access my previous conversations so that I can continue work seamlessly.

Conversation Features:

New Chat Creation:

* "+ New Chat" button always visible in sidebar  
* Creates fresh conversation with clean context  
* Auto-generates title from first query or user can customize  
* Keyboard shortcut: Ctrl/Cmd \+ N

Chat Organization:

* Automatic chronological grouping:  
  * Today  
  * Yesterday  
  * Last 7 days  
  * Last 30 days  
  * Older  
* Each chat preview shows:  
  * Title/summary  
  * Message count  
  * Last activity timestamp  
  * Preview of last message

Chat Management:

* Rename: Click on title to edit  
* Delete: Permanent removal with confirmation  
* Archive: Move to archive folder to reduce clutter  
* Pin: Pin important conversations to top  
* Export: Download as PDF or text file  
* Share: Share with colleagues (with permission controls)

Search Conversations:

* Full-text search across all conversations  
* Search within specific conversation  
* Filter by date range  
* Filter by documents used  
* Filter by department/project context  
* Highlighted search results

Context Persistence:

* Documents remain attached to conversation  
* Context maintained across sessions (survives logout)  
* Resume conversation from any device  
* Auto-save every few seconds

## **2.3.10 Collaboration Features**

Share Conversations  
User Story: As a team member, I want to share AI analysis with colleagues so that we can collaborate on complex tasks.

Sharing Options:

* Share button in conversation header  
* Select specific users or groups from directory  
* Permission levels:  
  * View only: Can read conversation and responses  
  * Comment: Can add comments without modifying  
  * Edit: Can add messages, upload documents, and query AI  
* Share link generation with optional expiration (1-90 days)  
* Email notifications to recipients  
* Revoke access anytime

Collaborative Features:

* Multiple users participate in same conversation  
* User identification badge on each message  
* Real-time updates when others add messages  
* Typing indicators showing active participants  
* Comment threads on specific AI responses  
* Team workspaces for department/project-based collaboration

Team Workspaces:

* Department-level shared conversation spaces  
* Project-specific chat rooms  
* Pre-loaded with relevant documents from DMSIQ  
* Team members auto-added based on project assignment  
* Shared knowledge accumulation for team learning

## **2.3.11 Response Enhancement Features**

Response Actions:

* Copy: Copy response text to clipboard  
* Regenerate: Request alternative response formulation  
* Edit prompt: Modify original query and regenerate  
* Share: Share specific response with others  
* Save: Bookmark important responses for quick access  
* Export: Download response as formatted document  
* Rate: Thumbs up/down for quality feedback  
* Report: Flag incorrect or problematic responses

Follow-Up Suggestions:

* AI suggests 3-4 related follow-up questions  
* Displayed as clickable chips below response  
* Based on conversation context and user department  
* Example: After tender summary → "Check eligibility criteria", "Analyze risks", "Compare with similar tenders"

Response Formatting:

* Clean, readable typography with proper spacing  
* Markdown rendering (headers, bold, italic, lists, links, quotes)  
* Syntax-highlighted code blocks  
* Formatted tables with borders  
* Collapsible sections for very long responses  
* Images and diagrams when relevant (for visual explanations)

---

## **2.4 Technical Requirements**

## **2.4.1 AI/ML Technology Stack**

Large Language Model:

* Primary: OpenAI GPT-4 / Azure OpenAI Service for advanced reasoning  
* Fallback: Anthropic Claude for alternative perspectives  
* Multilingual support for English and Hindi

Document Processing:

* Text extraction: Apache Tika for all document formats  
* OCR: Tesseract / Azure Form Recognizer for scanned documents  
* Table extraction: Specialized parsers for structured data  
* Embedding generation: OpenAI embeddings for semantic search  
* Vector database: Pinecone / Weaviate for fast retrieval

Natural Language Processing:

* Intent classification and entity recognition  
* Sentiment analysis for tone detection  
* Question reformulation for clarity  
* Language detection (English/Hindi)

Retrieval-Augmented Generation (RAG):

* Hybrid search (keyword \+ semantic similarity)  
* Dynamic context window management  
* Intelligent document chunking  
* Source attribution and citation

## **2.4.2 Performance Requirements**

Response Time:

* Simple queries: \< 2 seconds  
* Document analysis queries: \< 10 seconds  
* Multi-document comparison: \< 15 seconds  
* Document upload and processing: \< 30 seconds for typical documents  
* DMSIQ import: \< 5 seconds  
* Conversation loading: \< 1 second

Scalability:

* Support 1,000+ concurrent users  
* Handle 10,000+ daily queries  
* Process 5,000+ documents per day  
* 99.9% uptime availability

Resource Limits:

* Maximum conversation context: 128K tokens  
* User storage quota: 2 GB per user for conversation documents  
* Conversation retention: 2 years (configurable)  
* Processing queue: 100 concurrent document processing jobs

## **2.4.3 Security & Privacy**

Data Security:

* TLS 1.3 encryption for all communications  
* AES-256 encryption for stored conversations and documents  
* No persistent storage of sensitive data in AI model training  
* Secure document storage with access controls  
* Data anonymization for analytics

Access Control:

* Conversation-level permissions (private, shared, team)  
* Document-level permission verification from DMSIQ  
* Knowledge base access based on user role and department  
* Respect confidentiality levels in responses  
* Audit logging of all queries and document access

Content Safety:

* Input validation and sanitization  
* Output content filtering for inappropriate content  
* PII (Personally Identifiable Information) detection and masking  
* Compliance verification before sharing sensitive information  
* Rate limiting to prevent abuse

Compliance:

* GDPR compliance for data handling  
* Right to delete conversations and associated data  
* Data retention policy enforcement  
* Export user data on request  
* Audit trail for regulatory compliance

---

## **2.5 Analytics & Monitoring**

## **2.5.1 User Analytics (Personal Dashboard)**

Usage Metrics:

* Total queries made (daily, weekly, monthly)  
* Documents uploaded and analyzed  
* Conversations created  
* Time saved estimate  
* Most frequent query types  
* Response satisfaction ratings

## **2.5.2 Admin Analytics Dashboard**

System-Wide Metrics:

* Total queries across organization (shown on main dashboard)  
* Active users (daily, weekly, monthly)  
* Most common query categories and topics  
* Department-wise usage breakdown  
* Average response time and accuracy  
* User satisfaction ratings aggregated  
* Peak usage hours and patterns  
* Feature adoption rates (document upload, DMSIQ integration, sharing)  
* Failed queries and error analysis

AI Performance:

* Response accuracy metrics  
* User feedback aggregation (thumbs up/down ratio)  
* Query resolution rate  
* Model performance comparison  
* Knowledge gap identification  
* Frequently asked questions for FAQ creation

Insights Generation:

* Identify missing information in knowledge base  
* Suggest training topics based on query patterns  
* Department-specific needs and requirements  
* Document what users struggle to find  
* Optimization opportunities

---

## **2.6 Integration Points**

DMSIQ Integration:

* Bi-directional document access  
* Real-time permission checking  
* Folder structure navigation  
* Document metadata sync  
* Version control synchronization

TenderIQ Integration:

* Direct access to tender documents  
* Tender analysis queries routed to tender database  
* Automatic tender summarization  
* Bid preparation assistance  
* Compliance checking

Email Integration:

* Email conversation summaries  
* Scheduled AI analysis reports  
* Alert notifications for document insights  
* Forward documents via email for analysis

Calendar Integration:

* Extract deadlines from documents  
* Create calendar events for identified dates  
* Deadline reminders

---

## **2.7 Success Metrics**

## **2.7.1 Adoption Metrics**

* 80% of active users engage with Ask CeigallAI weekly  
* Average 50 queries per user per month  
* 60% of users upload documents for analysis  
* 40% of users import documents from DMSIQ

## **2.7.2 Performance Metrics**

* Average query response time \< 3 seconds  
* 95% of queries answered successfully  
* 90% document processing success rate  
* User satisfaction rating \> 4.2/5

## **2.7.3 Business Impact**

* 50% reduction in time spent searching for information  
* 50% faster document analysis compared to manual review  
* 30% improvement in bid preparation efficiency  
* 25% increase in cross-departmental knowledge sharing

## **2.7.4 Quality Metrics**

* 85% positive feedback (thumbs up) on AI responses  
* \< 5% queries requiring human support escalation  
* 90% accuracy in document information extraction  
* 80% of follow-up suggestions are relevant and useful

## **3\. TenderIQ Module**

## **3.1 Module Overview**

TenderIQ is a comprehensive AI-powered tender management system designed specifically for Ceigall's Tender & Bidding department to streamline the entire tender lifecycle from discovery to bid evaluation. The module automates tender monitoring from multiple government e-procurement portals, provides intelligent analysis, enables document comparison, facilitates bid evaluation, and maintains complete tender history with actionable insights.​

Module Access: Tender & Bidding Department only (can be extended to other departments by admin)

Key Value Proposition:

* Automated tender discovery from 50+ government portals  
* Real-time monitoring of high-value tenders (\>₹300 Cr)  
* AI-powered tender analysis and comparison  
* Bid document evaluation and compliance checking  
* Complete tender lifecycle tracking  
* 50% reduction in tender preparation time

---

## **3.2 Core Features**

## **3.2.1 Tender Discovery Dashboard**

User Story: As a tender executive, I want to see all high-value tenders from multiple portals in one place so that I never miss important opportunities.

Dashboard Overview:  
The Tender Discovery Dashboard serves as the central hub displaying all automatically scraped tenders from various e-procurement portals with comprehensive filtering, search, and status management capabilities.

Dashboard Layout:

Header Section:

* Page title: "Recent Activity" / "Tender Discovery"  
* Subtitle: "Access your previously analyzed tenders and comparisons"  
* Search bar: "Search tenders by title, number, or authority..."  
* Filter dropdowns:  
  * Status Filter: All Status, New, Reviewed, Shortlisted, Bid Submitted, Not Interested, Pending Results  
  * Category Filter: All Categories, Road Construction, Bridge Construction, Highway Development, Infrastructure, Building, Water Projects, etc.

Summary Cards (Top Row):  
Display key metrics at a glance:

1. Total Analyzed Card  
   * Icon: Document icon with number  
   * Metric: "5 Total Analyzed"  
   * Description: Total number of tenders analyzed  
2. Tenders Won Card  
   * Icon: Trophy/success icon  
   * Metric: "1 Tenders Won"  
   * Description: Successfully won tenders  
3. Total Value Card  
   * Icon: Currency icon (₹)  
   * Metric: "₹62.7 Cr Total Value"  
   * Description: Combined value of all analyzed tenders  
4. Pending Results Card  
   * Icon: Clock/calendar icon  
   * Metric: "1 Pending Results"  
   * Description: Tenders awaiting result announcements

Tender List View:

Tender Card Layout:  
Each tender displayed as a card with the following information:

Primary Information (Left Section):

* Checkbox for bulk selection  
* Star icon for marking favorites  
* Tender Title: Highway Construction & Maintenance \- NH44  
* Tender ID: PWD/NH-44/2024/ROAD/001  
* Issuing Authority: Public Works Department, Karnataka  
* Status Badge: "Under Evaluation" (color-coded: yellow/orange)  
* Category Badge: "Road Construction" (blue/green)

Financial & Timeline Information (Middle Section):

* Tender Value: ₹15.5 Cr (green, prominent)  
* Due Date: Due: 25 Apr 2024

Progress Indicator:

* Progress bar showing "Preparation Progress: 85%"  
* Visual bar with percentage completion

Action Buttons (Right Section):

* View Button: Opens detailed tender analysis  
* Export Button: Downloads tender details and analysis

Additional Tender Details (Expandable):  
Display comprehensive information from e-procurement portals:

Tender Identification:

* Serial Number (S. No)  
* Tender ID (unique identifier)  
* Name of the Work (full project description)  
* Employer/Authority details with complete address  
* State/Location

Tender Classification:

* Mode (Design Build, Item Rate, EPC, Tariff Base, etc.)  
* Estimated Project Cost (in Crores)

Timeline Information:

* e-Published Date (when tender was published on portal)  
* Tender Identification Date (when scraped by system)  
* Last Date for submission  
* BID Security amount in Crores

Project Specifications:

* Length in Km (for road/highway projects)  
* Per Km Cost (calculated)  
* Required Span Length (for bridges)  
* Amount of Road Work (in Crores)  
* Amount of Structure Work (in Crores)

Status Tracking:

* Review Status: Not Reviewed, Reviewed, Shortlisted  
* User Actions: Date when reviewed/shortlisted  
* Bid Status: Not Started, In Preparation, Submitted, Won, Lost  
* Result Status: Pending, L1 Obtained, Not Selected

---

## **3.2.2 Automated Tender Monitoring & Scraping**

User Story: As a business development manager, I want the system to automatically monitor and import tenders from government portals so that we don't miss opportunities.

Portal Integration:  
Automated web scraping from major e-procurement portals:

Government Portals (Pan-India):

* GeM (Government e-Marketplace)  
* eProcurement Portal (National Portal)  
* Central Public Procurement Portal (CPPP)  
* NHAI (National Highways Authority of India)  
* Indian Railways e-Procurement  
* Ministry of Road Transport and Highways (MoRTH)

State Government Portals:

* Maharashtra e-Tendering  
* Karnataka e-Procurement  
* Gujarat e-Procurement  
* Uttar Pradesh e-Procurement  
* Tamil Nadu Tenders  
* Other state portals (configurable)

Public Sector Undertakings:

* NTPC, NHPC, PGCIL  
* ONGC, GAIL  
* Coal India, NMDC  
* State Road Development Corporations

Scraping Configuration:

Filtering Criteria (Server-Side):

* Minimum Tender Value: ₹300 Crores (configurable threshold)  
* Categories: Road Construction, Bridge Construction, Highway Development, Infrastructure Projects  
* Geographic Focus: All India or specific states (configurable)  
* Tender Type: EPC, Design-Build, Item Rate, BOT, etc.  
* Bid Security Range: Filter by EMD/Bid Security requirements

Scraping Frequency:

* High-priority portals: Every 2 hours  
* Regular monitoring portals: Every 6 hours  
* Manual refresh option available  
* Real-time alerts for urgent tenders

Data Extraction:  
Automatically extract and structure the following information:

* Tender ID and reference number  
* Tender title and detailed description  
* Issuing organization with complete address  
* Employer/client details  
* Project location (State, District, specific area)  
* Tender category and work type  
* Estimated project cost  
* Bid security/EMD amount  
* Project specifications (length, span, scope)  
* Publication date and identification date  
* Bid submission deadline  
* Pre-bid meeting details (if any)  
* Document download links  
* Contact information

Duplicate Detection:

* Cross-portal duplicate identification  
* Amendment and corrigendum linking  
* Version control for updated tenders  
* Automatic consolidation of related notices

New Tender Notifications:

* Real-time email alerts for new high-value tenders  
* SMS notifications for urgent/critical tenders (deadline \< 7 days)  
* In-app notification center with badge counts  
* Daily digest email with summary of new tenders  
* Push notifications on mobile (future)

---

## **3.2.3 Tender Analysis Tool**

User Story: As a tender analyst, I want to upload and analyze tender documents using AI so that I can quickly understand requirements and prepare responses.

Interface Design (Analyze Tender Page):

Header:

* Back button: "Back to Modules"  
* Icon: Document icon (green)  
* Title: "Analyze Tender"  
* Subtitle: "AI-powered tender document analysis"

Upload Section:

Primary Upload Area:

* Section Title: "📄 Upload Tender Document"  
* Description: "Upload your tender document (PDF, DOC, ZIP, RAR formats supported) for AI-powered analysis and summarization"  
* Large dashed-border upload zone with document icon  
* Text: "Drop your tender document here"  
* Subtext: "or click to browse files (PDF, DOC, ZIP, RAR \- max 50MB)"  
* "Choose File" button (centered)

Sample Documents Section:

* Title: "Try Sample Documents"  
* Description: "Explore TenderIQ features with pre-loaded sample tender documents"  
* Sample tender cards:  
  * PWD Road Construction Tender 2024  
    * Highway development project \- ₹15 Cr value  
  * NHAI Bridge Construction RFP  
    * Steel bridge project \- ₹8 Cr value  
  * (Additional samples as available)

Analysis Features:

Automatic Document Processing:  
Once uploaded, the system automatically:

* Extracts text from PDF/DOC/scanned images (OCR)  
* Identifies document structure (sections, clauses, annexures)  
* Extracts tables, forms, and technical specifications  
* Generates document outline/table of contents  
* Identifies key dates and deadlines  
* Extracts financial information (estimated cost, EMD, performance guarantee)

AI-Powered Analysis Output:

1\. Executive Summary:

* High-level overview (3-5 paragraphs)  
* Project nature and scope  
* Key requirements at a glance  
* Critical success factors  
* Preliminary go/no-go recommendation

2\. Eligibility Criteria Extraction:

* Technical eligibility:  
  * Required experience (years, similar projects)  
  * Past project value thresholds  
  * Equipment requirements  
  * Personnel qualifications  
  * Technical certifications  
* Financial eligibility:  
  * Minimum turnover requirements  
  * Net worth criteria  
  * Banking arrangements  
* Legal eligibility:  
  * Registration requirements  
  * Licenses and permits  
  * Tax compliance certificates  
* Compliance Status: Auto-check against Ceigall's company profile  
* Gap Analysis: Highlight any unmet criteria

3\. Scope of Work Analysis:

* Detailed work breakdown  
* Deliverables list  
* Technical specifications summary  
* Quality standards and codes  
* Materials and equipment requirements  
* Manpower requirements  
* Project timeline and milestones

4\. Financial Analysis:

* Estimated project cost  
* Payment terms breakdown  
* Advance payment provisions  
* Price variation clauses  
* Retention money details  
* Performance bank guarantee amount  
* EMD/Bid security amount  
* Tax implications (GST structure)

5\. Timeline & Deadlines:

* Document purchase deadline  
* Pre-bid meeting date and venue  
* Site visit deadline  
* Query submission deadline  
* Bid submission deadline  
* Technical presentation date (if any)  
* Contract period/completion timeline  
* Milestone payment schedule

6\. Risk Assessment:  
Identify and categorize risks:

* Technical Risks:  
  * Complex/unfamiliar technology  
  * Aggressive technical specifications  
  * Resource capability gaps  
* Financial Risks:  
  * Unfavorable payment terms  
  * High retention percentages  
  * Limited price escalation  
  * Heavy bank guarantee burden  
* Legal Risks:  
  * Onerous penalty clauses  
  * Unfavorable indemnity clauses  
  * Dispute resolution concerns  
* Execution Risks:  
  * Tight project timeline  
  * Difficult site conditions  
  * Material availability concerns  
  * Monsoon/seasonal constraints

7\. Compliance Checklist:  
Auto-generated checklist with all required documents:

* Eligibility documents (registration, licenses, PAN, GST)  
* Technical documents (experience certificates, equipment list, key personnel CVs)  
* Financial documents (audited statements, turnover certificates, bank solvency)  
* Legal documents (affidavits, undertakings, power of attorney)  
* Bid security/EMD (DD/BG details)  
* Technical proposal documents  
* Financial proposal documents  
* Each item with checkbox and status indicator

8\. Key Clauses Extraction:

* Payment terms clause (with page reference)  
* Penalty/liquidated damages clause  
* Force majeure clause  
* Termination clause  
* Dispute resolution clause  
* Variation/change order clause  
* Warranty/defect liability clause  
* Highlighted Concerns: AI flags potentially unfavorable terms

9\. Evaluation Criteria:

* Technical evaluation parameters and weightage  
* Financial evaluation methodology  
* Qualification criteria  
* Selection process (QCBS, L1, etc.)  
* Scoring methodology

10\. Recommendations:

* Bid/No-Bid Recommendation: Based on eligibility, risk, and strategic fit  
* Win Probability Score: Percentage based on historical data  
* Preparation Complexity: Low/Medium/High  
* Required Resources: Estimated team size and timeline  
* Suggested Strategy: Approach for competitive positioning

Export Options:

* Download complete analysis as PDF report  
* Export specific sections  
* Save to DMSIQ for future reference  
* Share with team members

---

## **3.2.4 Tender Comparison Tool**

User Story: As a tender manager, I want to compare multiple tender documents side-by-side so that I can identify the best opportunities and understand differences.

Interface Design (Compare Tender Documents Page):

Header:

* Back button: "Back"  
* Title: "Compare Tender Documents"

Upload Interface (Side-by-Side):

First Document Section (Left):

* Title: "First Document"  
* Description: "Upload the first tender document for comparison"  
* Upload area:  
  * Document icon  
  * "Drop your first document here or click to browse"  
  * "Choose File" button  
* Sample Documents Panel:  
  * "Try with sample tender documents"  
  * Sample cards:  
    * PWD NH-44 Original Tender  
      * Highway construction \- ₹15.5 Cr value  
    * NHAI Bridge Construction RFP  
      * Steel bridge project \- ₹8 Cr value

Second Document Section (Right):

* Title: "Second Document"  
* Description: "Upload the second tender document for comparison"  
* Upload area (identical to first section)  
* Sample Documents Panel:  
  * Sample cards:  
    * PWD NH-44 Revised Tender  
      * Updated version \- ₹18.75 Cr value  
    * Mumbai Metro Construction Tender  
      * Metro rail project \- ₹12 Cr value

Compare Documents Button:

* Large centered button at bottom: "Compare Documents"  
* Activates after both documents uploaded

Comparison Analysis Output:

Once comparison is complete, display comprehensive side-by-side analysis:

1\. Quick Comparison Summary:  
Tabular view highlighting key differences:

| Parameter | Document 1 | Document 2 | Difference |
| :---- | :---- | :---- | :---- |
| Project Value | ₹15.5 Cr | ₹18.75 Cr | \+₹3.25 Cr |
| Bid Security | ₹31 Lakhs | ₹37.5 Lakhs | \+₹6.5 Lakhs |
| Completion Period | 24 months | 30 months | \+6 months |
| Payment Terms | 15 days | 30 days | \+15 days |
| Retention Money | 10% | 5% | \-5% |

2\. Eligibility Criteria Comparison:

* Technical requirements: Side-by-side comparison  
* Financial requirements: Highlight differences  
* Changed criteria: Clearly marked  
* New requirements: Highlighted in color  
* Removed requirements: Shown as strikethrough

3\. Scope Changes:

* Work items added/removed  
* Quantity variations  
* Specification changes  
* Technical requirement modifications

4\. Financial Terms Comparison:

* Cost estimate differences  
* Payment milestone changes  
* Price escalation clause variations  
* Retention and guarantee changes

5\. Timeline Comparison:

* Submission deadline differences  
* Contract period variations  
* Milestone timeline changes  
* Critical date changes highlighted

6\. Risk Comparison:

* New risks introduced  
* Mitigated risks  
* Overall risk score comparison  
* Recommendation on which tender is more favorable

7\. Clause-by-Clause Comparison:

* Payment terms comparison  
* Penalty clause differences  
* Changed legal terms  
* Modified dispute resolution  
* Variation in force majeure conditions

Export Comparison:

* Download comparison report as PDF  
* Export comparison matrix as Excel  
* Share with stakeholders

Use Cases:

* Compare original tender vs. amended tender  
* Compare similar tenders from different authorities  
* Compare current tender vs. historical similar tenders  
* Evaluate multiple opportunities simultaneously

---

## **3.2.5 Bid Evaluation Tool**

User Story: As an evaluation team member, I want to compare our bid documents against the tender requirements so that I can ensure full compliance before submission.

Interface Design (Evaluate Bid Documents Page):

Header:

* Back button: "Back"  
* Title: "Evaluate Bid Documents"

Upload Interface (Two Sections):

RFP/Tender Document Section (Top):

* Title: "RFP/Tender Document"  
* Description: "Upload the original tender/RFP document to evaluate against"  
* Upload area:  
  * Document icon  
  * "Drop tender document here or click to browse"  
  * "Choose Tender Document" button

Bid Documents Section (Bottom):

* Title: "Bid Documents"  
* Description: "Upload all your bid documents for evaluation"  
* Large upload area:  
  * Multiple document icon  
  * "Drop multiple bid documents here or click to browse"  
  * "Choose Bid Documents" button (supports multi-select)  
* Shows uploaded file list with remove option

Evaluate Bid Button:

* Large centered button at bottom: "Evaluate Bid"  
* Activates after RFP and at least one bid document uploaded

Evaluation Analysis Output:

1\. Compliance Matrix:  
Comprehensive checklist showing requirement vs. submission:

| Requirement | RFP Reference | Status | Our Submission | Page/Document | Remarks |
| :---- | :---- | :---- | :---- | :---- | :---- |
| Company Registration | Section 3.1 | ✓ Compliant | Certificate attached | Doc-1, Pg 5 | Valid till 2026 |
| Turnover Certificate | Section 3.2 | ✓ Compliant | Audited statement | Doc-2, Pg 12 | ₹250 Cr avg |
| Experience Certificate | Section 3.3 | ⚠️ Partial | 3 projects listed | Doc-3, Pg 8 | Need 1 more |
| Equipment List | Section 4.1 | ✓ Compliant | Detailed list | Doc-5, Pg 15-18 | All equipment listed |
| Key Personnel CV | Section 4.2 | ❌ Missing | Not found | \- | Action required |

Status Indicators:

* ✓ Compliant (Green): Requirement fully met  
* ⚠️ Partial (Yellow): Partially met, needs attention  
* ❌ Missing (Red): Requirement not addressed  
* ⊘ Not Applicable (Gray): Not relevant to our bid

2\. Gap Analysis:  
Critical Issues section highlighting:

* Missing Documents: List of required but not submitted documents  
* Incomplete Submissions: Documents submitted but lacking required details  
* Non-Compliance: Where our submission doesn't meet specified criteria  
* Formatting Issues: Documents not in required format  
* Signature/Authorization: Missing signatures or authorizations  
* Validity Issues: Expired certificates or documents

3\. Technical Proposal Evaluation:

* Methodology compliance check  
* Technical specification matching  
* Resource plan adequacy  
* Quality assurance plan review  
* Project timeline validation  
* Risk mitigation plan assessment

4\. Financial Proposal Evaluation:

* BOQ completeness check  
* Price schedule format compliance  
* Tax calculation verification  
* Payment terms acknowledgment  
* Bid security/EMD confirmation

5\. Document Organization Check:

* Index/table of contents verification  
* Page numbering compliance  
* Document sequencing as per RFP  
* File naming convention adherence  
* Digital signature verification (for online bids)

6\. Pre-Submission Checklist:  
Auto-generated final checklist before submission:

*  All mandatory documents uploaded  
*  All documents signed and dated  
*  Bid security/EMD enclosed  
*  Technical proposal sealed  
*  Financial proposal sealed  
*  No prices in technical proposal  
*  All amendments acknowledged  
*  Addendum incorporated  
*  Declaration and undertakings signed  
*  Format compliance verified

7\. Risk Flags:

* High Risk: Critical non-compliance that may lead to rejection  
* Medium Risk: Issues that may affect scoring  
* Low Risk: Minor formatting or documentation issues

8\. Recommendations:

* Overall Bid Quality Score: Percentage (e.g., 85% \- Good)  
* Readiness Status: Ready to Submit / Needs Revision / Not Ready  
* Action Items: Prioritized list of what needs to be fixed  
* Estimated Time to Fix: Time needed to address gaps  
* Risk Assessment: Probability of bid rejection based on gaps

Real-Time Feedback:  
As documents are uploaded and processed:

* Progress indicator for each document processing  
* Real-time compliance checking  
* Instant alerts for missing critical documents  
* Suggestions for improvement

Export Options:

* Download evaluation report (PDF)  
* Export compliance matrix (Excel)  
* Generate submission checklist (PDF)  
* Create gap analysis report for team

---

## **3.2.6 Tender History & Tracking**

User Story: As a tender coordinator, I want to view all previously analyzed tenders with their current status so that I can track our tender pipeline.

Interface Design (Recent Activity/Tender History Page):

Header:

* Title: "Recent Activity"  
* Subtitle: "Access your previously analyzed tenders and comparisons"

Tender History Section:

* Section Icon: Document list icon  
* Section Title: "Tender History"  
* Description: "View and manage all your analyzed tender documents"

Search & Filter Bar:

* Search Box: "Search tenders by title, number, or authority..."  
* Status Filter Dropdown: "All Status" with options:  
  * All Status  
  * New (newly scraped, not reviewed)  
  * Reviewed (analyzed but no decision)  
  * Shortlisted (marked for bidding)  
  * Bid In Preparation (actively working on bid)  
  * Bid Submitted (submitted to authority)  
  * Under Evaluation (with client)  
  * Won (bid successful)  
  * Lost (bid unsuccessful)  
  * Not Interested (decided not to bid)  
  * Pending Results (awaiting result announcement)  
* Category Filter Dropdown: "All Categories" with options:  
  * All Categories  
  * Road Construction  
  * Bridge Construction  
  * Highway Development  
  * Building Construction  
  * Water Projects  
  * Power Projects  
  * Infrastructure  
  * Maintenance Works  
  * EPC Projects

Summary Statistics Cards:  
Top row displaying 4 metric cards:

1. Total Analyzed  
   * Icon: Document count icon (blue)  
   * Number: 5  
   * Label: "Total Analyzed"  
2. Tenders Won  
   * Icon: Trophy icon (green)  
   * Number: 1  
   * Label: "Tenders Won"  
3. Total Value  
   * Icon: Currency icon (purple/pink)  
   * Number: ₹62.7 Cr  
   * Label: "Total Value"  
4. Pending Results  
   * Icon: Clock/calendar icon (orange)  
   * Number: 1  
   * Label: "Pending Results"

Tender Card List:  
Each tender displayed as an expandable card:

Card Header:

* Checkbox (left) for bulk selection  
* Star icon (favorite/bookmark toggle)  
* Tender title (bold, large): "Highway Construction & Maintenance \- NH44"  
* Three-dot menu icon (right) for actions: Edit, Delete, Duplicate, Archive

Card Content (Line 2):

* Tender ID: PWD/NH-44/2024/ROAD/001  
* Issuing Authority: Public Works Department, Karnataka

Status & Category Badges (Line 3):

* Status badge (colored pill): "Under Evaluation" (orange/yellow background)  
* Category badge (colored pill): "Road Construction" (blue/green background)

Financial & Timeline (Line 4):

* Tender Value (green, prominent): ₹15.5 Cr  
* Dot separator  
* Due Date: "Due: 25 Apr 2024"

Progress Indicator:

* Progress label: "Preparation Progress"  
* Progress bar (visual): 85% filled (blue bar)  
* Percentage: 85%

Action Buttons (Right Side):

* View Button: Eye icon \+ "View" (opens detailed analysis)  
* Export Button: Download icon \+ "Export" (downloads tender data)

Additional Information (Expandable):  
Click to expand and show full tender details from scraping:

* Serial Number  
* Complete tender description  
* Employer full address  
* State and exact location  
* Mode (Design Build, Item Rate, etc.)  
* Estimated Project Cost  
* e-Published Date  
* Tender Identification Date (when scraped)  
* Last Date for submission  
* BID Security in Cr.  
* Length in Km (for road/highway)  
* Per Km Cost  
* Required Span Length (for bridges)  
* Amount of Road Work  
* Amount of Structure Work  
* Review status (Not Reviewed/Reviewed/Shortlisted)  
* Review date and reviewer name  
* Internal notes/comments

Bulk Actions:  
When tenders are selected via checkboxes:

* Change Status (dropdown)  
* Mark as Favorite/Remove Favorite  
* Export Selected  
* Archive Selected  
* Delete Selected

Sorting Options:

* Sort by: Newest First, Oldest First, Value (High to Low), Value (Low to High), Deadline (Upcoming), Status

Pagination:

* Items per page: 10, 25, 50, 100  
* Page navigation at bottom

---

## **3.2.7 Tender Detail View**

User Story: As a user, I want to see comprehensive details of a specific tender so that I have all information needed for decision-making.

Page Layout:

Header Section:

* Back button to Tender History  
* Tender title (large)  
* Tender ID and issuing authority  
* Last updated timestamp

Tab Navigation:

* Overview: Executive summary and key information  
* Analysis: Complete AI analysis  
* Documents: All related documents  
* Timeline: Critical dates and milestones  
* Financial: Cost breakdown and payment terms  
* Compliance: Eligibility and checklist  
* Team: Assigned team members and tasks  
* Notes: Internal comments and discussions  
* History: Activity log and status changes

Overview Tab:

* Quick facts panel  
* Status and category badges  
* Key metrics (value, deadline, location)  
* Progress indicators  
* Quick actions (Edit Status, Assign Team, Add Notes, Export)

Analysis Tab:

* Complete AI-generated analysis  
* All sections from Tender Analysis Tool  
* Editable sections for manual updates  
* Version history of analysis

Documents Tab:

* Original tender document(s) with viewer  
* Our bid documents (if uploaded)  
* Supporting documents  
* Comparison reports  
* Download all option

Timeline Tab:

* Visual timeline/Gantt chart  
* All critical dates marked  
* Countdown to submission deadline  
* Milestone tracking for bid preparation  
* Automatic reminders setup

Financial Tab:

* Estimated project cost breakdown  
* EMD/bid security details  
* Performance guarantee calculation  
* Payment terms visualization  
* Cash flow projection  
* ROI analysis (if won probability estimates available)

Compliance Tab:

* Detailed eligibility criteria  
* Ceigall's compliance status against each  
* Missing documents list  
* Compliance percentage score  
* Action items for achieving full compliance

Team Tab:

* Assigned team members with roles  
* Task assignment and tracking  
* Responsibility matrix  
* Collaboration space  
* Activity feed for team

Notes Tab:

* Threaded discussion  
* @mention team members  
* Attach files to notes  
* Mark notes as important  
* Search within notes

History Tab:

* Complete audit trail  
* Status changes with timestamps and users  
* Document uploads/modifications  
* Analysis updates  
* Team assignments  
* Export history

Floating Action Button:

* Quick access to common actions  
* Change Status  
* Assign Team  
* Upload Documents  
* Add Note  
* Share Tender  
* Export Report

---

## **3.3 Technical Requirements**

## **3.3.1 Web Scraping Infrastructure**

Scraping Technology:

* Python-based scrapers using BeautifulSoup, Scrapy, Selenium  
* Headless browser automation (Puppeteer/Playwright) for JavaScript-heavy portals  
* Proxy rotation for avoiding IP blocks  
* CAPTCHA solving integration (when required)  
* Robust error handling and retry mechanisms

Data Processing Pipeline:

* Raw HTML parsing and cleaning  
* Structured data extraction  
* Data validation and normalization  
* Deduplication across portals  
* Storage in relational database (PostgreSQL)  
* Indexing in Elasticsearch for fast search

Monitoring & Alerts:

* Scraper health monitoring  
* Failed scrape detection and alerts  
* Data quality checks  
* Portal structure change detection  
* Daily scraping summary reports

## **4.3.2 AI/ML Technology**

Document Analysis:

* Large Language Model (LLM): OpenAI GPT-4 / Azure OpenAI  
* Document parsing: Apache Tika for text extraction  
* OCR: Tesseract / Azure Form Recognizer for scanned documents  
* Table extraction: Specialized parsers  
* NLP: spaCy for entity recognition  
* Embeddings: For semantic search and comparison

Analysis Features:

* Clause extraction using NER  
* Risk identification using sentiment and keyword analysis  
* Compliance checking against knowledge base  
* Comparison using vector similarity  
* Summarization using abstractive techniques

## **4.3.3 Database Schema**

Tenders Table (Core):

* tender\_id (Primary Key, UUID)  
* tender\_ref\_number (String, unique)  
* tender\_title (Text)  
* description (Text, full description)  
* employer\_name (String)  
* employer\_address (Text)  
* issuing\_authority (String)  
* state (String)  
* location (String)  
* category (String)  
* mode (String: Design Build, Item Rate, EPC, etc.)  
* estimated\_cost (Decimal, in Crores)  
* bid\_security (Decimal, in Crores)  
* length\_km (Decimal, nullable)  
* per\_km\_cost (Decimal, nullable)  
* span\_length (Decimal, nullable)  
* road\_work\_amount (Decimal, nullable)  
* structure\_work\_amount (Decimal, nullable)  
* e\_published\_date (Date)  
* identification\_date (Date, when scraped)  
* submission\_deadline (DateTime)  
* prebid\_meeting\_date (DateTime, nullable)  
* site\_visit\_deadline (Date, nullable)  
* portal\_source (String)  
* portal\_url (String)  
* document\_url (String)  
* status (Enum: New, Reviewed, Shortlisted, Bid\_Preparation, Submitted, Won, Lost, Not\_Interested, Pending\_Results)  
* review\_status (Enum: Not\_Reviewed, Reviewed, Shortlisted)  
* reviewed\_by (Foreign Key to Users, nullable)  
* reviewed\_at (Timestamp, nullable)  
* created\_at (Timestamp)  
* updated\_at (Timestamp)  
* is\_favorite (Boolean)  
* is\_archived (Boolean)

Tender\_Analysis Table:

* analysis\_id (Primary Key, UUID)  
* tender\_id (Foreign Key)  
* executive\_summary (Text)  
* eligibility\_criteria (JSON)  
* scope\_of\_work (Text)  
* financial\_analysis (JSON)  
* timeline\_analysis (JSON)  
* risk\_assessment (JSON)  
* compliance\_checklist (JSON)  
* key\_clauses (JSON)  
* evaluation\_criteria (Text)  
* recommendations (Text)  
* win\_probability (Float, 0-100)  
* analyzed\_at (Timestamp)  
* analyzed\_by (Foreign Key to Users)

Tender\_Documents Table:

* document\_id (Primary Key, UUID)  
* tender\_id (Foreign Key)  
* document\_name (String)  
* document\_type (Enum: Original\_RFP, Amendment, Bid\_Document, Supporting, Comparison\_Report)  
* file\_path (String)  
* file\_size (Integer)  
* uploaded\_by (Foreign Key to Users)  
* uploaded\_at (Timestamp)

Tender\_Comparisons Table:

* comparison\_id (Primary Key, UUID)  
* tender\_1\_id (Foreign Key)  
* tender\_2\_id (Foreign Key)  
* comparison\_report (JSON)  
* created\_by (Foreign Key to Users)  
* created\_at (Timestamp)

Tender\_Team Table:

* assignment\_id (Primary Key, UUID)  
* tender\_id (Foreign Key)  
* user\_id (Foreign Key)  
* role (String: Lead, Analyst, Technical, Financial, etc.)  
* assigned\_at (Timestamp)  
* assigned\_by (Foreign Key to Users)

Tender\_Notes Table:

* note\_id (Primary Key, UUID)  
* tender\_id (Foreign Key)  
* user\_id (Foreign Key)  
* note\_content (Text)  
* parent\_note\_id (Foreign Key, nullable, for threading)  
* created\_at (Timestamp)  
* is\_important (Boolean)

Tender\_Activity\_Log Table:

* activity\_id (Primary Key, UUID)  
* tender\_id (Foreign Key)  
* user\_id (Foreign Key)  
* action\_type (String: Created, Viewed, Analyzed, Status\_Changed, Document\_Uploaded, etc.)  
* action\_details (JSON)  
* timestamp (Timestamp)

## **3.3.4 Performance Requirements**

Response Times:

* Tender list loading: \< 2 seconds  
* Single tender detail view: \< 1 second  
* Document upload: \< 5 seconds for typical files (\< 50 MB)  
* AI analysis generation: \< 60 seconds for typical tender document  
* Comparison generation: \< 90 seconds for two documents  
* Bid evaluation: \< 2 minutes for complete evaluation  
* Search results: \< 1 second

Scalability:

* Support 100+ concurrent users  
* Store 10,000+ tender records  
* Process 500+ tender documents per month  
* Handle 1000+ daily scraping operations  
* 99.9% uptime for tender monitoring

## **3.3.5 Security & Access Control**

Data Security:

* Encryption at rest (AES-256) for sensitive tender documents  
* Encryption in transit (TLS 1.3)  
* Secure file storage with access control  
* Audit logging of all tender access

Access Control:

* Role-based access: Admin, Tender Manager, Tender Executive, Analyst, Viewer  
* Tender-level permissions (view, edit, delete, share)  
* Document-level access control  
* Department-based filtering (only Tender & Bidding dept by default)

Compliance:

* Tender data retention policy (minimum 7 years for audit)  
* Sensitive information handling (financial data, proprietary analysis)  
* GDPR compliance for user data  
* Audit trails for all actions

---

## **3.4 Integration Points**

DMSIQ Integration:

* Save tender documents to DMSIQ automatically  
* Import tender-related documents from DMSIQ  
* Link analyzed tenders to project folders in DMSIQ  
* Access historical bid documents from DMSIQ

Ask CeigallAI Integration:

* Quick "Ask AI about this tender" button  
* Pre-loaded tender context in chat  
* Access tender analysis from AI chat  
* Query specific clauses or requirements via chat

Email Integration:

* Email notifications for new tenders  
* Daily tender digest emails  
* Deadline reminders  
* Team collaboration via email  
* Export and email reports

Calendar Integration:

* Sync tender deadlines to Outlook/Google Calendar  
* Pre-bid meeting reminders  
* Milestone tracking for bid preparation  
* Result announcement date tracking

External Portal Integration:

* Direct links to original tender on source portal  
* Auto-login to portals (where possible) for document download  
* Status sync from portal (if API available)

---

## **3.5 Success Metrics**

## **3.5.1 Adoption Metrics**

* 100% of Tender & Bidding team uses TenderIQ daily  
* 90% of tenders discovered through automated scraping (vs. manual search)  
* 80% of tender documents analyzed using AI  
* Average 5 tender comparisons per week

## **3.5.2 Efficiency Metrics**

* 50% reduction in tender discovery time (from 2 hours to 1 hour daily)  
* 60% faster tender analysis (from 4 hours to 1.5 hours per tender)  
* 40% reduction in bid preparation time  
* 70% faster compliance checking (from 2 hours to 30 minutes)

## **3.5.3 Quality Metrics**

* 95% accuracy in tender data extraction from portals  
* 90% accuracy in AI-generated eligibility criteria extraction  
* 85% accuracy in risk identification  
* \< 2% bid rejections due to compliance issues (down from 8%)

## **3.5.4 Business Impact**

* 30% increase in tender submissions (due to better discovery and efficiency)  
* 15% improvement in bid success rate (due to better analysis and compliance)  
* ₹500+ Cr tender pipeline value maintained at all times  
* 25% improvement in team capacity (can handle more tenders)

## **4\. DMSIQ (Data Management Service Intelligence Quotient)**

## **4.1 Module Overview**

DMSIQ is a centralized, AI-powered document management system that provides intelligent organization, advanced search capabilities, and role-based access control for all Ceigall documents. The module displays department-specific documents with AI-powered summarization, version control, and seamless integration with Ask CeigallAI and TenderIQ modules.​

Module Access: Universal \- Available to all registered users with department-based filtering

Key Value Proposition:

* Centralized document repository for all departments  
* AI-powered document summarization on-demand  
* Department-based automatic access control  
* Advanced search and filtering capabilities  
* Integration with other modules for seamless workflow  
* Version control and audit trail  
* 70% reduction in document search time

---

## **4.2 Core Features**

## **4.2.1 Document Library Dashboard**

User Story: As a user, I want to see all documents relevant to my department in an organized manner so that I can quickly find what I need.

Dashboard Layout:

Header Section:

* Page title: "DMSIQ \- Document Library"  
* Breadcrumb navigation: Home \> DMSIQ  
* Upload button (prominent): "+ Upload Document"  
* User's current department indicator

Search & Filter Bar:

* Global Search: "Search documents by name, content, or tags..."  
* Department Filter: Dropdown showing user's department by default  
  * My Department (auto-selected based on user profile)  
  * All Departments (if user has cross-department access)  
  * Tender & Bidding  
  * Contracts & Legal  
  * Human Resources  
  * Finance & Billing  
  * Procurement  
  * Project Management  
  * Administration  
  * Shared with Me  
* File Type Filter: All Types, PDF, DOC/DOCX, Excel, PPT, Images, CAD Files, Archives  
* Date Filter: All Time, Today, Last 7 Days, Last 30 Days, Last 3 Months, Last Year, Custom Range  
* Sort By: Name (A-Z), Name (Z-A), Date Modified (Newest), Date Modified (Oldest), Size (Largest), Size (Smallest)

View Options:

* Toggle between Grid View and List View (icons in top-right)  
* Items per page: 12, 24, 48, 96 (for grid view)  
* Pagination controls at bottom

Summary Statistics (Optional Top Bar):  
Display key metrics:

* Total Documents: Count of documents in current view/filter  
* Storage Used: GB/TB used in department  
* Recent Uploads: Documents uploaded in last 7 days  
* Shared Documents: Number of documents shared with user

---

## **4.2.2 Document Display Views**

Grid View Layout:

Document Card (for Grid View):  
Each document displayed as a card in responsive grid (3-4 columns):

Card Header:

* Document thumbnail/icon based on file type:  
  * PDF: Red PDF icon  
  * Word: Blue DOC icon  
  * Excel: Green XLS icon  
  * PowerPoint: Orange PPT icon  
  * Image: Image preview thumbnail  
  * CAD: Technical drawing icon  
  * Archive: ZIP icon  
  * Unknown: Generic file icon  
* Checkbox (top-left corner) for bulk selection  
* Star icon (top-right corner) for favorites/bookmarks

Card Body:

* Document name (truncated with ellipsis, max 2 lines)  
* File size (e.g., "2.5 MB")  
* Upload date (e.g., "Oct 28, 2025" or "2 days ago")  
* Uploader name (e.g., "Uploaded by John Doe")  
* Department badge (colored pill): "Tender & Bidding"

Card Footer (Action Buttons):

* Preview Button: Eye icon (opens document viewer)  
* AI Summary Button: Sparkle/AI icon (opens AI summary popup)  
* Download Button: Download icon  
* More Options: Three-dot menu with additional actions:  
  * View Details  
  * Share  
  * Move  
  * Rename  
  * Delete  
  * Version History  
  * Copy Link

List View Layout:

Document Row (for List View):  
Tabular display with columns:

| Select | Name | Type | Size | Modified | Uploaded By | Department | Actions |
| :---- | :---- | :---- | :---- | :---- | :---- | :---- | :---- |
| ☐ | Highway\_Tender\_2024.pdf | PDF | 5.2 MB | Oct 28, 2025 | John Doe | Tender & Bidding | \[Preview\] \[AI Summary\] \[Download\] \[...\] |

Columns:

* Select: Checkbox for bulk operations  
* Name: Document name with file icon, clickable to preview  
* Type: File extension badge  
* Size: File size in MB/KB  
* Modified: Last modified date and time  
* Uploaded By: User who uploaded the document  
* Department: Department tag/badge  
* Actions: Quick action buttons (Preview, AI Summary, Download, More options)

Hover Effects:

* Card/row highlights on hover  
* Action buttons appear/emphasize on hover  
* Quick preview thumbnail on hover (for images)

---

## **4.2.3 Document Upload**

User Story: As a user, I want to upload documents to DMSIQ so that they're stored centrally and accessible to my team.

Upload Interface:

Upload Button Click → Opens Upload Modal:

Modal Header:

* Title: "Upload Documents"  
* Close button (X)

Upload Area:

* Large dashed-border drop zone  
* Upload icon (cloud with arrow)  
* Primary text: "Drop your documents here"  
* Secondary text: "or click to browse files"  
* Supported formats note: "Supports PDF, DOC, DOCX, XLS, XLSX, PPT, PPTX, Images, CAD files, ZIP (max 100MB per file)"  
* "Choose Files" button (centered)  
* Multiple file selection supported

Upload Configuration:

Required Fields:

* Document Name: Auto-filled from filename, editable  
* Department: Dropdown (defaults to user's department)  
  * User's Department (default)  
  * Other departments (if user has permission)  
* Category: Dropdown to classify document  
  * Tender Documents  
  * Contracts & Agreements  
  * Technical Specifications  
  * Financial Documents  
  * HR Documents  
  * Project Plans  
  * Reports  
  * Correspondence  
  * Presentations  
  * Other

Optional Fields:

* Tags: Add custom tags (comma-separated or tag chips)  
* Description: Brief description of document content  
* Project/Tender Reference: Link to specific project or tender  
* Confidentiality Level: Dropdown  
  * Public (all department members)  
  * Internal (department only)  
  * Confidential (specific roles)  
  * Restricted (specific users)  
* Expiry Date: Set document expiration (for time-sensitive docs)

Upload Progress:

* File list showing each selected file  
* Individual progress bars for each file  
* Status indicators: Uploading, Processing, Complete, Failed  
* Cancel button for each upload  
* Remove button to deselect files before upload

Upload Completion:

* Success message with document count  
* "View Uploaded Documents" button  
* "Upload More" button  
* Auto-close modal after 3 seconds (optional)

Automatic Processing:  
After upload, system automatically:

* Extracts text content for indexing  
* Generates thumbnail preview  
* Performs virus/malware scan  
* Extracts metadata (author, creation date, etc.)  
* Applies OCR for scanned documents  
* Generates AI summary (queued for background processing)  
* Assigns permissions based on department and confidentiality level

---

## **4.2.4 AI Summary Feature**

User Story: As a user, I want to view an AI-generated summary of any document so that I can quickly understand its content without reading the entire file.

Triggering AI Summary:

* Click "AI Summary" button on document card/row  
* Button shows sparkle/stars icon with "AI Summary" label  
* Keyboard shortcut: Select document and press "S"

AI Summary Popup/Modal:

Modal Structure:

Header:

* Title: "AI-Powered Document Summary"  
* Document name below title (with icon)  
* Close button (X) in top-right

Body Section (Scrollable):

Summary Status:  
If summary not yet generated:

* Loading indicator with message: "Generating AI summary..."  
* Progress animation  
* Estimated time: "This may take 30-60 seconds"

If summary ready:  
Display Summary Content:

1\. Quick Overview (Top Section):

* Document Type: Auto-detected (Contract, Tender, Report, Specification, etc.)  
* Key Topic: Main subject matter identified by AI  
* Summary Length: Word/page count  
* Generated On: Timestamp when summary was created  
* Language: Detected language (English, Hindi, etc.)

2\. Executive Summary:

* 3-5 paragraph high-level overview  
* Covers main points and key takeaways  
* Written in clear, concise language  
* Bullet points for key highlights

3\. Key Information Extracted:  
Structured information cards based on document type:

For Tender Documents:

* Tender ID and Authority  
* Estimated Project Cost  
* Bid Security/EMD Amount  
* Submission Deadline  
* Eligibility Requirements  
* Key Technical Specifications

For Contracts:

* Parties Involved  
* Contract Value  
* Contract Period  
* Payment Terms  
* Key Obligations  
* Penalty Clauses  
* Termination Conditions

For Technical Specifications:

* Technical Requirements  
* Standards and Codes  
* Material Specifications  
* Quality Parameters  
* Testing Requirements

For Financial Documents:

* Financial Year/Period  
* Key Amounts and Values  
* Budget Allocations  
* Variances (if applicable)  
* Approval Status

For Reports:

* Report Period  
* Key Findings  
* Recommendations  
* Action Items  
* Critical Issues

4\. Important Dates & Deadlines:

* Extracted dates presented in timeline format  
* Highlighted critical deadlines  
* Countdown to upcoming deadlines (if applicable)

5\. Key Entities Mentioned:

* Organizations/Companies  
* People (names and roles)  
* Locations  
* Projects referenced  
* Related documents

6\. Risk Flags (if applicable):

* Potential concerns identified by AI  
* Compliance issues  
* Missing information  
* Unclear clauses  
* Conflicting information

7\. Document Sections/Structure:

* Table of contents  
* Section summaries  
* Page references for key information

8\. Tags & Keywords:

* AI-generated tags  
* Key terminology used  
* Related topics

9\. Confidence Score:

* AI confidence level in summary accuracy (0-100%)  
* Data quality indicator  
* Note if OCR was used (may affect accuracy)

Footer Actions:

* Copy Summary: Copy entire summary to clipboard  
* Download Summary: Download as PDF or TXT  
* Regenerate: Request fresh AI summary  
* Share Summary: Share via email or with team members  
* Full Document: Button to open full document viewer  
* Feedback: Thumbs up/down for summary quality

Summary Options (Gear/Settings Icon):

* Summary Length: Short (1 para), Medium (default, 3-5 paras), Detailed (comprehensive)  
* Focus Areas: Select what to emphasize (financial, technical, legal, timeline)  
* Language: Summary language preference (English, Hindi)

AI Summary Behavior:

First Request:

* If document newly uploaded and summary not generated  
* Show loading state while AI processes document  
* Generate summary in background  
* Store summary in database for future quick access

Subsequent Requests:

* Load cached summary instantly (\< 1 second)  
* Show "Last updated" timestamp  
* Option to regenerate if document was modified

Summary Quality Indicators:

* High confidence: Green indicator  
* Medium confidence: Yellow indicator (e.g., for scanned/low-quality documents)  
* Low confidence: Orange indicator with warning about potential inaccuracies

Error Handling:

* If AI summary generation fails: Show error message with option to retry  
* If document is too large: Show message "Document exceeds size limit for AI summarization"  
* If document is encrypted/password-protected: Show message "Cannot generate summary for protected documents"  
* If document format not supported: Show message "Summary not available for this file type"

---

## **4.2.5 Document Viewer**

User Story: As a user, I want to preview documents without downloading them so that I can quickly verify content.

Opening Document Viewer:

* Click document name or Preview button  
* Opens in modal overlay or new tab (user preference)

Viewer Interface:

Header:

* Document name (large, prominent)  
* Close button (X) or Back button  
* Action toolbar:  
  * Download button  
  * Print button  
  * Share button  
  * AI Summary button (quick access)  
  * Full screen toggle  
  * Zoom controls (+, \-, fit to width, fit to page)

Main Viewer Area:

* Document rendered based on file type:  
  * PDF: Embedded PDF viewer with page navigation  
  * Images: High-resolution image display with zoom/pan  
  * Office Docs: Converted preview (using Office Online viewer or similar)  
  * Text Files: Formatted text display with syntax highlighting (if code)  
  * Videos: Video player with controls  
  * Audio: Audio player  
  * Unsupported: Download prompt with file info

PDF Viewer Features:

* Page navigation (previous, next, jump to page)  
* Page thumbnails sidebar (collapsible)  
* Search within document  
* Zoom controls and fit options  
* Rotate page  
* Full screen mode  
* Print selection

Side Panel (Optional, Collapsible):

* Document details (metadata)  
* Version history  
* Comments/annotations  
* AI summary (quick view)  
* Related documents

Keyboard Shortcuts:

* Arrow keys: Navigate pages  
* \+/- : Zoom in/out  
* F: Full screen  
* Esc: Close viewer  
* Ctrl+F: Search

---

## **4.2.6 Advanced Search & Filtering**

User Story: As a user, I want to search for documents using various criteria so that I can find exactly what I need quickly.

Global Search Bar:

* Prominent search bar at top  
* Placeholder: "Search documents by name, content, or tags..."  
* Search icon on left  
* Clear button (X) on right when typing  
* Real-time suggestions dropdown as user types

Search Capabilities:

1\. Full-Text Search:

* Search within document content (indexed text)  
* Searches document names, descriptions, tags  
* Searches metadata (author, comments)  
* Boolean operators support (AND, OR, NOT)  
* Phrase search with quotes ("exact phrase")  
* Wildcard support (project\*)

2\. Filter Sidebar (Advanced Filters):  
Collapsible sidebar with filter categories:

Department Filter:

* Checkboxes for each department  
* "My Department" quick filter  
* "All Departments" option

File Type Filter:

* Checkboxes for common types  
* PDF, Word, Excel, PowerPoint  
* Images, CAD, Archives, Others

Date Range Filter:

* Quick filters: Today, Last 7 days, Last month, Last year  
* Custom date range picker (from \- to)  
* Filter by upload date or modified date (toggle)

Size Filter:

* Small (\< 1 MB)  
* Medium (1-10 MB)  
* Large (10-100 MB)  
* Very Large (\> 100 MB)  
* Custom size range

Uploader Filter:

* Search and select from user list  
* Show documents uploaded by specific users  
* "Uploaded by me" quick filter

Tag Filter:

* Show all tags used in system  
* Multi-select tags  
* Tag cloud visualization

Project/Tender Reference:

* Filter by associated project  
* Filter by tender ID  
* Dropdown or autocomplete search

Confidentiality Level:

* Public, Internal, Confidential, Restricted

Status Filter:

* Active, Archived, Expired  
* Has AI Summary / No AI Summary  
* Favorite / Not Favorite

3\. Saved Searches:

* Save frequently used search queries  
* Name saved searches  
* Quick access to saved searches dropdown  
* Edit and delete saved searches

4\. Search Results:

* Result count displayed  
* Matching text highlighted in previews  
* Relevance score (optional)  
* Sort results by relevance, date, name, size  
* Export search results list

5\. Recent Searches:

* Dropdown showing last 10 searches  
* Quick repeat of previous searches  
* Clear search history option

---

## **4.2.7 Document Organization**

User Story: As a user, I want to organize documents using folders and tags so that related documents are grouped logically.

Folder Structure:

Left Sidebar (Folder Tree):

* My Documents: Personal folder  
* Department Folders: Automatically created for each department  
  * Tender & Bidding  
    * Active Tenders  
    * Completed Tenders  
    * Templates  
  * Contracts & Legal  
    * Active Contracts  
    * Archived Contracts  
    * Templates  
  * \[Other departments...\]  
* Shared with Me: Documents others have shared  
* Favorites: Starred/bookmarked documents  
* Recent: Recently viewed documents  
* Trash: Deleted documents (retention period: 30 days)

Folder Actions:

* Create new folder (+ button)  
* Rename folder (right-click menu)  
* Delete folder (moves to trash)  
* Move folder (drag and drop)  
* Share folder with team members  
* Set folder permissions

Document Organization Actions:

* Move: Select document(s) → Move to folder  
* Copy: Duplicate document to another folder  
* Tag: Add/remove tags for categorization  
* Favorite: Star important documents  
* Archive: Move old documents to archive

Bulk Operations:

* Select multiple documents via checkboxes  
* Bulk move to folder  
* Bulk add tags  
* Bulk download (creates ZIP)  
* Bulk delete  
* Bulk share

Tagging System:

* Add multiple tags per document  
* Auto-suggest existing tags while typing  
* Create new tags on the fly  
* Tag management (rename, merge, delete tags)  
* Color-coded tags (optional)  
* Tag-based filtering and search

---

## **4.2.8 Version Control**

User Story: As a user, I want to track document versions so that I can access previous versions if needed and see modification history.

Version Control Features:

Automatic Versioning:

* New version created when document is re-uploaded with same name  
* Version numbering: v1, v2, v3, etc. or v1.0, v1.1, v2.0  
* Each version stores:  
  * Version number  
  * Upload date and time  
  * Uploaded by (user name)  
  * File size  
  * Change description (optional, user-provided)

Version History Access:

* "Version History" button in document actions menu  
* Opens version history panel/modal

Version History Panel:

Layout:

* Timeline view showing all versions  
* Most recent version at top  
* Each version entry shows:  
  * Version number  
  * Date and time  
  * Uploaded by user name  
  * File size and size change (± MB)  
  * Change description/comment  
  * Actions: View, Download, Restore, Compare

Version Actions:

* View: Open that version in viewer  
* Download: Download specific version  
* Restore: Make this version current (creates new version)  
* Compare: Compare two versions side-by-side (for text documents)  
* Delete Version: Remove specific version (admin only)

Version Comparison:

* Select two versions to compare  
* Side-by-side or unified diff view  
* Highlighted changes (additions in green, deletions in red)  
* Page-by-page comparison for PDFs

Version Notifications:

* Notify users when new version is uploaded (for watched documents)  
* Email alerts for critical document updates  
* Version change log in activity feed

---

## **4.2.9 Document Sharing & Permissions**

User Story: As a user, I want to share documents with specific colleagues or teams so that we can collaborate effectively.

Sharing Options:

Share Button Click → Opens Share Modal:

Modal Structure:

Share With:

* Specific Users: Search and select from employee directory  
* Groups/Teams: Share with department, project team, or custom group  
* Share Link: Generate shareable link (with optional password and expiry)

Permission Levels:

* View Only: Can only view and download  
* Comment: Can view, download, and add comments  
* Edit: Can view, download, edit, and re-upload  
* Full Control: Can view, edit, share, and delete

Advanced Sharing Options:

* Set expiry date for shared access  
* Require password for link access  
* Disable download (view only, no download)  
* Track who accessed the document  
* Revoke access anytime

Share Settings:

* Email notification to recipients  
* Custom message with share invitation  
* Allow recipients to reshare (yes/no)

Shared Document Indicators:

* Shared icon/badge on document card  
* "Shared with me" section in sidebar  
* List of current sharers in document details

Share Activity Log:

* Track who accessed shared document  
* View date and time of access  
* See who downloaded the document  
* Export share activity report

---

## **4.2.10 Document Details & Metadata**

User Story: As a user, I want to view complete document information including metadata so that I understand document context.

Document Details Panel:  
Access via "View Details" in document actions menu or click info icon.

Details Panel Layout:

Basic Information:

* Document name (editable)  
* File type and icon  
* File size  
* Full file path/location in folder structure

Upload Information:

* Uploaded by (user name and profile picture)  
* Upload date and time  
* Modified by (if different from uploader)  
* Last modified date and time  
* Number of versions

Classification:

* Department assignment  
* Category/document type  
* Tags (editable)  
* Project/tender reference  
* Confidentiality level

Content Metadata:

* Number of pages (for documents)  
* Word count (for text documents)  
* Duration (for audio/video)  
* Dimensions (for images)  
* Author (extracted from document properties)  
* Creation date (from document properties)  
* Language detected

AI-Generated Metadata:

* Automatically extracted keywords  
* Document summary (link to full AI summary)  
* Detected entities (people, organizations, dates)  
* Related documents (AI suggestions)

Sharing & Access:

* Current share status  
* List of users with access  
* Permission levels assigned  
* Share link if generated

Activity History:

* Views count  
* Downloads count  
* Recent activity log:  
  * Viewed by \[User\] on \[Date\]  
  * Downloaded by \[User\] on \[Date\]  
  * Shared with \[User\] on \[Date\]  
  * Version \[X\] uploaded on \[Date\]

Storage Information:

* Storage location (server/cloud path \- for admin)  
* Checksum/hash (for integrity verification)  
* Backup status

Actions in Details Panel:

* Edit metadata  
* Add to favorites  
* Move to different folder  
* Download  
* Share  
* Delete  
* Generate AI summary (if not already done)

---

## **4.2.11 Integration with Other Modules**

Integration with Ask CeigallAI:

Quick Access:

* "Ask AI about this document" button on each document  
* Opens Ask CeigallAI with document pre-loaded  
* User can immediately query the document  
* Context automatically set to document content

From Chat to DMSIQ:

* In Ask CeigallAI, "Import from DMSIQ" button  
* Opens DMSIQ browser in modal  
* User selects documents to add to conversation  
* Documents appear in chat's documents panel

Bi-directional Sync:

* Documents uploaded in chat can be saved to DMSIQ  
* DMSIQ documents can be queried in Ask CeigallAI  
* Share conversation insights back to document as comments

Integration with TenderIQ:

Tender Document Linking:

* Link DMSIQ documents to specific tenders  
* Auto-save tender documents from TenderIQ to DMSIQ  
* Tender folder automatically created in DMSIQ  
* Access tender documents from TenderIQ interface

Document Categorization:

* Tender documents automatically tagged  
* Project/tender reference maintained  
* Easy retrieval of all documents related to a tender

Bid Document Management:

* Store all bid documents in DMSIQ  
* Link to tender analysis in TenderIQ  
* Version control for bid iterations  
* Compliance document checklist sync

---

## **4.3 Technical Requirements**

## **4.3.1 Storage Architecture**

Storage Solution:

* Cloud object storage (AWS S3, Azure Blob Storage, Google Cloud Storage)  
* Multi-tier storage for cost optimization:  
  * Hot tier: Recently accessed documents (\< 30 days)  
  * Cool tier: Occasionally accessed (30-180 days)  
  * Archive tier: Rarely accessed (\> 180 days)  
* Automatic tiering based on access patterns  
* Geographic redundancy for disaster recovery

Storage Specifications:

* Initial storage allocation: 5 TB per department  
* Scalable up to 100 TB  
* Per-user quota: 10 GB (configurable)  
* File size limits: 100 MB per file (configurable)  
* Total files supported: 1 million+ documents

## **4.3.2 Document Processing Pipeline**

Upload Processing:

1. Virus/malware scan (ClamAV or similar)  
2. File validation and sanitization  
3. Metadata extraction  
4. Text extraction (Apache Tika)  
5. OCR processing for scanned documents (Tesseract/Azure Form Recognizer)  
6. Thumbnail generation  
7. Document indexing in Elasticsearch  
8. AI summary generation (queued, background job)  
9. Storage in appropriate tier  
10. Notification to user

Processing Performance:

* Small files (\< 1 MB): \< 5 seconds  
* Medium files (1-10 MB): \< 30 seconds  
* Large files (10-100 MB): \< 2 minutes  
* Background AI summary: \< 5 minutes

## **4.3.3 Search Technology**

Search Infrastructure:

* Elasticsearch for full-text search and indexing  
* Supports 1 million+ documents  
* Real-time indexing (\< 5 seconds after upload)  
* Fuzzy search and typo tolerance  
* Multi-language support (English, Hindi)  
* Synonym support  
* Faceted search (filter by metadata)

Search Performance:

* Search query response: \< 500 ms for most queries  
* Search with filters: \< 1 second  
* Complex searches: \< 2 seconds  
* Autocomplete suggestions: \< 100 ms

## **4.3.4 AI/ML Technology**

AI Summary Generation:

* Large Language Model (LLM): OpenAI GPT-4 / Azure OpenAI  
* Chunk-based processing for large documents  
* Parallel processing for faster generation  
* Caching of generated summaries  
* Incremental updates for modified documents

Document Intelligence:

* Named Entity Recognition (NER) for metadata extraction  
* Document classification (tender, contract, report, etc.)  
* Key phrase extraction  
* Language detection  
* Related document recommendations using embeddings

## **4.3.5 Database Schema**

Documents Table:

* document\_id (Primary Key, UUID)  
* document\_name (String)  
* file\_path (String, storage location)  
* file\_type (String)  
* file\_size (Integer, in bytes)  
* department (String)  
* category (String)  
* confidentiality\_level (Enum: Public, Internal, Confidential, Restricted)  
* uploaded\_by (Foreign Key to Users)  
* uploaded\_at (Timestamp)  
* modified\_by (Foreign Key to Users, nullable)  
* modified\_at (Timestamp)  
* description (Text, nullable)  
* project\_reference (String, nullable)  
* tender\_reference (Foreign Key to Tenders, nullable)  
* is\_favorite (Boolean)  
* is\_archived (Boolean)  
* views\_count (Integer)  
* downloads\_count (Integer)  
* current\_version (Integer)  
* has\_ai\_summary (Boolean)  
* checksum (String, file hash for integrity)

Document\_Versions Table:

* version\_id (Primary Key, UUID)  
* document\_id (Foreign Key)  
* version\_number (Integer)  
* file\_path (String)  
* file\_size (Integer)  
* uploaded\_by (Foreign Key to Users)  
* uploaded\_at (Timestamp)  
* change\_description (Text, nullable)

Document\_Tags Table:

* tag\_id (Primary Key, UUID)  
* document\_id (Foreign Key)  
* tag\_name (String)  
* created\_at (Timestamp)

Document\_Shares Table:

* share\_id (Primary Key, UUID)  
* document\_id (Foreign Key)  
* shared\_by (Foreign Key to Users)  
* shared\_with\_user (Foreign Key to Users, nullable)  
* shared\_with\_group (String, nullable)  
* permission\_level (Enum: View, Comment, Edit, Full\_Control)  
* share\_link (String, nullable)  
* share\_password (String, nullable, encrypted)  
* expires\_at (Timestamp, nullable)  
* created\_at (Timestamp)

Document\_AI\_Summaries Table:

* summary\_id (Primary Key, UUID)  
* document\_id (Foreign Key)  
* summary\_type (Enum: Short, Medium, Detailed)  
* summary\_content (Text)  
* key\_information (JSON)  
* extracted\_entities (JSON)  
* confidence\_score (Float, 0-100)  
* generated\_at (Timestamp)  
* generated\_by (String, model version)

Document\_Activity\_Log Table:

* activity\_id (Primary Key, UUID)  
* document\_id (Foreign Key)  
* user\_id (Foreign Key)  
* action\_type (Enum: Viewed, Downloaded, Shared, Modified, Deleted)  
* action\_timestamp (Timestamp)  
* ip\_address (String)  
* user\_agent (String)

Folders Table:

* folder\_id (Primary Key, UUID)  
* folder\_name (String)  
* parent\_folder\_id (Foreign Key to Folders, nullable)  
* department (String)  
* created\_by (Foreign Key to Users)  
* created\_at (Timestamp)  
* is\_system\_folder (Boolean)

Document\_Folders Table:

* document\_id (Foreign Key)  
* folder\_id (Foreign Key)  
* added\_at (Timestamp)

## **4.3.6 Performance Requirements**

Response Times:

* Document list loading: \< 2 seconds  
* Document preview: \< 3 seconds  
* Document upload: \< 10 seconds for typical files  
* AI summary generation: \< 5 minutes (background)  
* Cached AI summary display: \< 1 second  
* Search results: \< 1 second  
* Filter application: \< 500 ms  
* Document download: Based on file size and network speed

Scalability:

* Support 500+ concurrent users  
* Store 100,000+ documents per department  
* Handle 1,000+ daily uploads  
* Process 10,000+ AI summary requests per day  
* 99.9% uptime SLA

## **4.3.7 Security & Access Control**

Data Security:

* Encryption at rest (AES-256)  
* Encryption in transit (TLS 1.3)  
* Encrypted file storage  
* Secure file deletion (data wiping)  
* Regular security audits

Access Control:

* Role-based access control (RBAC)  
* Department-based default permissions  
* Document-level granular permissions  
* Folder-level inheritance  
* Confidentiality level enforcement  
* Audit trail for all access

Compliance:

* Document retention policy (7 years minimum)  
* Secure deletion after retention period  
* GDPR compliance for personal data  
* ISO 27001 compliance  
* Audit logs for compliance reporting

---

## **4.4 User Interface Specifications**

## **4.4.1 Responsive Design**

Desktop View:

* Three-column layout: Folder tree (left), Document grid/list (center), Details panel (right)  
* Responsive grid: 3-4 columns based on screen width  
* Collapsible sidebars to maximize viewing area

Tablet View:

* Two-column layout: Documents and details  
* Folder tree as drawer/overlay  
* 2-3 column grid for documents

Mobile View (Future):

* Single column layout  
* Bottom navigation bar  
* Swipe gestures for actions  
* Simplified document cards

## **4.4.2 Accessibility**

WCAG 2.1 Level AA Compliance:

* Keyboard navigation support  
* Screen reader compatibility  
* High contrast mode  
* Focus indicators  
* Alt text for images and icons  
* Sufficient color contrast ratios  
* Resizable text

## **4.4.3 User Experience Enhancements**

Performance Optimization:

* Lazy loading for document thumbnails  
* Pagination for large document sets  
* Virtual scrolling for smooth performance  
* Progressive image loading  
* Cached document previews

Visual Feedback:

* Loading indicators for all async operations  
* Toast notifications for success/error messages  
* Progress bars for uploads  
* Skeleton screens while loading  
* Smooth transitions and animations

---

## **4.5 Success Metrics**

## **4.5.1 Adoption Metrics**

* 95% of users access DMSIQ at least weekly  
* Average 15 document views per user per day  
* 70% of documents uploaded have AI summaries generated  
* 50% of users use AI summary feature regularly

## **4.5.2 Efficiency Metrics**

* 70% reduction in document search time (from 5 min to 1.5 min)  
* 60% reduction in document retrieval time  
* 80% of searches return relevant results in top 10  
* Average document upload time \< 10 seconds

## **4.5.3 Usage Metrics**

* 500+ documents uploaded per week across organization  
* 2,000+ document views per day  
* 1,000+ AI summaries generated per week  
* 200+ document shares per week  
* 90% of uploaded documents are properly tagged and categorized

## **4.5.4 Quality Metrics**

* 90%+ user satisfaction with search functionality  
* 85%+ accuracy in AI-generated summaries (based on user feedback)  
* \< 0.1% document corruption or loss incidents  
* 99.9% system uptime

## **4.5.5 Business Impact**

* Centralized document repository reduces duplicate storage by 40%  
* Improved compliance with document retention policies  
* Enhanced collaboration through document sharing (30% increase)  
* Faster onboarding for new employees (access to all necessary documents)  
* Better audit readiness with comprehensive activity logs

