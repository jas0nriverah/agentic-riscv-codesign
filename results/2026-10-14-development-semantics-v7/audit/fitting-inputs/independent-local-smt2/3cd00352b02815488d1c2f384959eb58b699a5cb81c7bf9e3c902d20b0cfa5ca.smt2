(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_1 () (_ BitVec 32))
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x46 (bvadd (bvshl independent_opaque_0 (bvand (_ bv2 32) (_ bv31 32))) independent_opaque_1)))
(let ((?x47 (bvadd (bvsub (_ bv0 32) independent_opaque_0) ?x46)))
(let ((?x45 (bvadd (bvshl independent_opaque_0 (bvand (_ bv1 32) (_ bv31 32))) independent_opaque_0)))
(let ((?x37 (bvadd ?x45 independent_opaque_1)))
(and (distinct ?x37 ?x47) true))))))
(check-sat)
