(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x424 (bvshl independent_opaque_0 (bvand (_ bv5 32) (_ bv31 32)))))
(let ((?x48 (bvadd independent_opaque_0 ?x424)))
(let ((?x67 (bvadd ?x424 independent_opaque_0)))
(and (distinct ?x67 ?x48) true)))))
(check-sat)
