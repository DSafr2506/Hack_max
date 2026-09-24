export type EventType = "olympiad" | "school" | "hackathon" | "career";
export type Grade = 8 | 9 | 10 | 11;
export interface City {
  id: string;
  name: string;
  region: string;
}
export interface Profile {
  grade: Grade | null;
  cityId: string;
  types: EventType[];
  goalText: string;
  completed: boolean;
}
export type Value = string | number | boolean;
export interface CommonEvent {
  id: string;
  title: string;
  description: string;
  organizer: string;
  format: string;
  region: string;
  eligibleRegions: string[];
  grades: Grade[];
  goals: string[];
  results: string[];
  opens: string;
  deadline: string;
  start: string;
  end: string;
  duration: number;
  cost: string;
  price: number;
  participation: string;
  accessible?: boolean;
  parentalConsent?: boolean;
  travel?: boolean;
  accommodation?: boolean;
  admission: string;
  level: string;
  organizerType: string;
  direction: string;
  verified?: boolean;
  source?: string;
}
export interface OlympiadFields {
  status: string;
  subject: string;
  stage: string;
  onlineSelection?: boolean;
  university: string;
  benefit: string;
}
export interface SchoolFields {
  schoolDirection: string;
  selection: string;
  quotaRegion: string;
  season: string;
  achievements?: boolean;
}
export interface HackathonFields {
  stack: string;
  teamSize: number;
  teamSearch?: boolean;
  experience: string;
  prizeFund: number;
  mentors?: boolean;
}
export interface CareerFields {
  industry: string;
  company: string;
  activity: string;
  targeted?: boolean;
  minAge: number;
  transfer?: boolean;
}
export type Opportunity = CommonEvent &
  (
    | { type: "olympiad"; special: OlympiadFields }
    | { type: "school"; special: SchoolFields }
    | { type: "hackathon"; special: HackathonFields }
    | { type: "career"; special: CareerFields }
  );
export interface Filters {
  types: EventType[];
  goals: string[];
  values: Record<string, Value[]>;
  ranges: Record<string, { min?: string; max?: string }>;
  regionOnly: boolean;
  soon: boolean;
  special: Record<string, Value[]>;
  specialRanges: Record<string, { min?: string; max?: string }>;
}
export interface Field {
  key: string;
  label: string;
  options?: Value[];
  kind?: "boolean" | "number" | "date";
  unit?: string;
}
