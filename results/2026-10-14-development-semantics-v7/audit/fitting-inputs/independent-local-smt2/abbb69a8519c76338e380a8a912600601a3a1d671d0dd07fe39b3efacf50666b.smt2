(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_1 () (_ BitVec 32))
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x1103 (bvadd independent_opaque_0 (bvsub (_ bv0 32) (bvshl independent_opaque_1 (bvand (_ bv31 32) (_ bv31 32)))))))
(let ((?x155 (bvshl independent_opaque_1 (bvand (_ bv31 32) (_ bv31 32)))))
(let ((?x328 (bvadd independent_opaque_0 ?x155)))
(and (distinct ?x328 ?x1103) true)))))
(check-sat)
