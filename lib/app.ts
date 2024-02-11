#!/usr/bin/env node
import { App } from "aws-cdk-lib";
import { MothershipStack } from "./stacks/mothership-stack";

const ACCOUNT_NO = "735029168602";
const REGION = "us-east-2";

const app = new App();

const mothershipStack = new MothershipStack(
  app,
  `MothershipStack-${ACCOUNT_NO}-${REGION}`,
  {}
);

app.synth();
