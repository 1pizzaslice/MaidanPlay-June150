export type Access = "edit" | "confirm" | "view";
export type Role = "employee" | "coach" | "kush" | "amit" | "akash" | "admin" | "viewer";
export type Stage = "draft" | "pending_amit" | "pending_akash" | "approved";
export type Status = "r" | "p" | "g";

export type User = {
  name: string;
  email: string;
  mobile?: string | null;
  access: Access;
  role: Role;
  batch?: string | null;
};

export type Student = {
  id: string;
  first?: string;
  last?: string;
  batch: string;
  dob?: string;
  gender?: string;
  school?: string;
  pincode?: string;
  parent?: string;
  phone?: string;
  email?: string;
  jersey?: string;
  cup?: string;
  amount?: string;
  age?: string;
};

export type FieldDef = {
  key: string;
  label: string;
  src?: string;
  o1?: string;
  o2?: string;
  o3?: string;
  input?: "text" | "num" | "date" | "select" | "school" | "phones";
  extra?: string;
  type?: "cleared" | "yesno" | "choice" | "select" | "value" | "text";
  choices?: string[];
  when?: string;
  greenOn?: string;
  optional?: boolean;
};

export type ConfirmValue = {
  opt?: "o1" | "o2";
  val?: string;
  rel?: string;
};

export type Workflow = {
  stage?: Stage;
  confirm?: Record<string, ConfirmValue>;
  coachConfirm?: { ok?: boolean; by?: string; at?: string };
  amit?: Record<string, unknown>;
  akash?: Record<string, unknown>;
  kyp?: Record<string, unknown> & { published?: boolean; publishedBy?: string; publishedAt?: string };
  comment?: { text: string; by: string; at: string } | null;
  submittedBy?: string | null;
  submittedAt?: string | null;
  amitBy?: string | null;
  amitAt?: string | null;
  akashBy?: string | null;
  akashAt?: string | null;
  closedAt?: string | null;
  sentBack?: string | null;
  sentBackBy?: string | null;
  sentBackAt?: string | null;
  sentBackTo?: string | null;
  _meta?: Record<string, unknown>;
};

export type BatchConfig = {
  coach: string;
  employees: string[];
};

export type AppConfig = {
  users: User[];
  batchcfg: Record<string, BatchConfig>;
  batchOrder: string[];
  org: {
    employees: string[];
    pnlHead: { name: string; role: string };
    director: { name: string; role: string };
    founder: { name: string; role: string };
  };
  accessLabel: Record<string, string>;
  roleLabel: Record<string, string>;
  stage: Record<string, Stage>;
  stageLabel: Record<Stage, string>;
  confirmFields: FieldDef[];
  amitFields: FieldDef[];
  akashFields: FieldDef[];
  detailFields: string[];
  kypFields: FieldDef[];
  greenTarget: number;
  super: string[];
};

export type Bootstrap = {
  ok: boolean;
  user: User;
  students: Student[];
  verify: Record<string, Workflow>;
  config: AppConfig;
};
