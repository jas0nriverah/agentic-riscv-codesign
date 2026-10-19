(set-logic QF_BV)
(set-option :timeout 500)
; benchmark generated from python API
(set-info :status unknown)
(declare-fun independent_opaque_0 () (_ BitVec 32))
(assert
 (let ((?x1153 (bvadd (bvshl independent_opaque_0 (bvand (_ bv16 32) (_ bv31 32))) (_ bv4294901760 32))))
(let ((?x424 (bvand (_ bv16 32) (_ bv31 32))))
(let ((?x703 (bvshl (bvadd independent_opaque_0 (_ bv4294967295 32)) ?x424)))
(and (distinct ?x703 ?x1153) true)))))
(check-sat)
