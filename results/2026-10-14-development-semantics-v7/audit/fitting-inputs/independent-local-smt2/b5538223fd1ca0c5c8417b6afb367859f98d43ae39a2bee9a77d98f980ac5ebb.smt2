(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_1 () (_ BitVec 32))
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x328 (bvadd (bvsub (_ bv0 32) (bvshl independent_opaque_1 (bvand (_ bv2 32) (_ bv31 32)))) (bvsub (_ bv0 32) (bvshl independent_opaque_1 (bvand (_ bv4 32) (_ bv31 32)))))))
(let ((?x1340 (bvadd independent_opaque_0 ?x328)))
(let ((?x878 (bvand (_ bv2 32) (_ bv31 32))))
(let ((?x756 (bvshl (bvadd (bvshl independent_opaque_1 ?x878) independent_opaque_1) ?x878)))
(let ((?x222 (bvsub independent_opaque_0 ?x756)))
(and (distinct ?x222 ?x1340) true)))))))
(check-sat)
