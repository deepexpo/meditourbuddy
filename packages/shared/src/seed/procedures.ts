import type { procedureCategoryEnum } from "../schema.js";

interface ProcedureSeed {
  code: string;
  name: string;
  category: (typeof procedureCategoryEnum.enumValues)[number];
  typicalVisits: number;
  recoveryDaysOnsite: number;
}

export const procedures: ProcedureSeed[] = [
  {
    code: "IMPLANT_SINGLE",
    name: "Single Dental Implant",
    category: "implant",
    typicalVisits: 2,
    recoveryDaysOnsite: 3,
  },
  {
    code: "IMPLANT_ALL_ON_4",
    name: "All-on-4 Full Arch Implants",
    category: "implant",
    typicalVisits: 2,
    recoveryDaysOnsite: 5,
  },
  {
    code: "IMPLANT_ALL_ON_6",
    name: "All-on-6 Full Arch Implants",
    category: "implant",
    typicalVisits: 2,
    recoveryDaysOnsite: 5,
  },
  {
    code: "CROWN_ZIRCONIA",
    name: "Zirconia Crown",
    category: "restorative",
    typicalVisits: 1,
    recoveryDaysOnsite: 1,
  },
  {
    code: "CROWN_EMAX",
    name: "E-max Crown",
    category: "restorative",
    typicalVisits: 1,
    recoveryDaysOnsite: 1,
  },
  {
    code: "VENEER_EMAX",
    name: "E-max Veneer",
    category: "cosmetic",
    typicalVisits: 1,
    recoveryDaysOnsite: 1,
  },
  {
    code: "VENEER_ZIRCONIA",
    name: "Zirconia Veneer",
    category: "cosmetic",
    typicalVisits: 1,
    recoveryDaysOnsite: 1,
  },
  {
    code: "ROOT_CANAL",
    name: "Root Canal Treatment",
    category: "restorative",
    typicalVisits: 1,
    recoveryDaysOnsite: 1,
  },
  {
    code: "FULL_MOUTH_RECON",
    name: "Full Mouth Reconstruction",
    category: "surgical",
    typicalVisits: 2,
    recoveryDaysOnsite: 7,
  },
  {
    code: "BONE_GRAFT",
    name: "Bone Graft",
    category: "surgical",
    typicalVisits: 1,
    recoveryDaysOnsite: 4,
  },
  {
    code: "SINUS_LIFT",
    name: "Sinus Lift",
    category: "surgical",
    typicalVisits: 1,
    recoveryDaysOnsite: 5,
  },
  {
    code: "TEETH_WHITENING",
    name: "Teeth Whitening",
    category: "cosmetic",
    typicalVisits: 1,
    recoveryDaysOnsite: 0,
  },
];
