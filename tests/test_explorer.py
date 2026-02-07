from csdl_explore.explorer import CSDLExplorer


def test_get_picklist_usage():
    xml = """<?xml version="1.0" encoding="utf-8"?>
    <edmx:Edmx Version="1.0" xmlns:edmx="http://schemas.microsoft.com/ado/2007/06/edmx">
      <edmx:DataServices m:DataServiceVersion="2.0" xmlns:m="http://schemas.microsoft.com/ado/2007/08/dataservices/metadata">
        <Schema Namespace="SFOData" xmlns="http://schemas.microsoft.com/ado/2008/09/edm"
                xmlns:sap="http://www.sap.com/Protocols/SAPData">
          <EntityType Name="EmpJob">
            <Key><PropertyRef Name="userId"/></Key>
            <Property Name="userId" Type="Edm.String"/>
            <Property Name="status" Type="Edm.String" sap:visible="true"
                      sap:label="Status"/>
          </EntityType>
          <EntityType Name="PerPersonal">
            <Key><PropertyRef Name="personIdExternal"/></Key>
            <Property Name="personIdExternal" Type="Edm.String"/>
            <Property Name="gender" Type="Edm.String" sap:visible="true"
                      sap:label="Gender"/>
          </EntityType>
        </Schema>
      </edmx:DataServices>
    </edmx:Edmx>"""
    explorer = CSDLExplorer(xml)
    usage = explorer.get_picklist_usage()
    assert isinstance(usage, dict)
    assert len(usage) == 0
