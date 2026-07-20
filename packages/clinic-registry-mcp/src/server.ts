import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import {
  compareProcedures,
  compareProceduresInputSchema,
  compareProceduresOutputSchema,
} from "./tools/compare-procedures.js";
import {
  getClinicProfile,
  getClinicProfileInputSchema,
  getClinicProfileOutputSchema,
} from "./tools/get-clinic-profile.js";
import {
  listProcedures,
  listProceduresInputSchema,
  listProceduresOutputSchema,
} from "./tools/list-procedures.js";
import {
  searchClinics,
  searchClinicsInputSchema,
  searchClinicsOutputSchema,
} from "./tools/search-clinics.js";
import {
  verifyAccreditation,
  verifyAccreditationInputSchema,
  verifyAccreditationOutputSchema,
} from "./tools/verify-accreditation.js";

export function createServer() {
  const server = new McpServer({
    name: "clinic-registry-mcp",
    version: "0.1.0",
  });

  server.registerTool(
    "list_procedures",
    {
      title: "List Procedures",
      description:
        "Reference lookup of dental procedures, optionally filtered by category, so free-text intake can be mapped to a procedure_code.",
      inputSchema: listProceduresInputSchema,
      outputSchema: listProceduresOutputSchema,
    },
    async (input) => {
      const output = await listProcedures(input);
      return {
        content: [{ type: "text", text: JSON.stringify(output) }],
        structuredContent: output,
      };
    },
  );

  server.registerTool(
    "search_clinics",
    {
      title: "Search Clinics",
      description:
        "Find vetted clinics matching a case (procedure, country, budget, language, accreditation requirement).",
      inputSchema: searchClinicsInputSchema,
      outputSchema: searchClinicsOutputSchema,
    },
    async (input) => {
      const output = await searchClinics(input);
      return {
        content: [{ type: "text", text: JSON.stringify(output) }],
        structuredContent: output,
      };
    },
  );

  server.registerTool(
    "get_clinic_profile",
    {
      title: "Get Clinic Profile",
      description:
        "Full detail for one clinic: accreditations, practitioners, and priced procedures.",
      inputSchema: getClinicProfileInputSchema,
      outputSchema: getClinicProfileOutputSchema,
    },
    async (input) => {
      const output = await getClinicProfile(input);
      return {
        content: [{ type: "text", text: JSON.stringify(output) }],
        structuredContent: output,
      };
    },
  );

  server.registerTool(
    "compare_procedures",
    {
      title: "Compare Procedures",
      description:
        "Cross-clinic price comparison for one procedure, optionally against a Canadian quote.",
      inputSchema: compareProceduresInputSchema,
      outputSchema: compareProceduresOutputSchema,
    },
    async (input) => {
      const output = await compareProcedures(input);
      return {
        content: [{ type: "text", text: JSON.stringify(output) }],
        structuredContent: output,
      };
    },
  );

  server.registerTool(
    "verify_accreditation",
    {
      title: "Verify Accreditation",
      description:
        "The trust tool — returns the evidence chain (source_url, validity) for a clinic's accreditations, not just a boolean.",
      inputSchema: verifyAccreditationInputSchema,
      outputSchema: verifyAccreditationOutputSchema,
    },
    async (input) => {
      const output = await verifyAccreditation(input);
      return {
        content: [{ type: "text", text: JSON.stringify(output) }],
        structuredContent: output,
      };
    },
  );

  return server;
}
