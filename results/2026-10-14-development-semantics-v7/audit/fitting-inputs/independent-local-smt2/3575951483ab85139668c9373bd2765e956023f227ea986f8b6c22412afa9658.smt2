(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x1103 (bvadd independent_opaque_0 (bvsub (_ bv0 32) (bvshl independent_opaque_0 (bvand (_ bv2 32) (_ bv31 32)))))))
(let ((?x1340 (bvshl independent_opaque_0 (bvand (_ bv2 32) (_ bv31 32)))))
(let ((?x958 (bvsub independent_opaque_0 ?x1340)))
(and (distinct ?x958 ?x1103) true)))))
(check-sat)
